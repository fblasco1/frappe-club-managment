"""Servicio de reservas externas online (guest + token).

Spec: `club_management/specs/reservas_espacio_externo.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from club_management.spaces.availability import (
	assert_no_overlap_with_occupancy,
	find_occupancy_conflicts,
	get_occupancy,
	validate_time_range,
)
from club_management.spaces.services.confirmacion_reservas import _is_pdf_file
from club_management.spaces.services.externo_tokens import (
	generate_token_acceso,
	sign_sesion_token,
	verify_sesion_token,
)
from club_management.spaces.services.portal_reservas import (
	ITEM_ALQUILER_SOCIO,
	SLOT_DURACION_MINUTOS,
	SLOT_FIN_MINUTOS,
	SLOT_INICIO_MINUTOS,
	_as_hhmmss,
	_combo_con,
	_format_minutes,
	_imagen_espacio,
	_slot_is_occupied,
)

ITEM_ALQUILER_EXTERNO = ITEM_ALQUILER_SOCIO  # ICDPE-ALQ-ARS-TEMP
RESERVA_DOCTYPE = "Reserva Espacio"

CHANNEL_DISABLED_CODE = "CHANNEL_DISABLED"
CHANNEL_DISABLED_MESSAGE = "Canal de alquileres externo deshabilitado"
CHANNEL_DISABLED_BODY: dict[str, str] = {
	"status": "error",
	"code": CHANNEL_DISABLED_CODE,
	"message": CHANNEL_DISABLED_MESSAGE,
}


def _deny() -> None:
	frappe.throw(_("Not permitted"), frappe.PermissionError)


def raise_channel_disabled() -> None:
	"""HTTP 403 estructurado cuando el canal guest está apagado."""
	frappe.local.response["http_status_code"] = 403
	frappe.local.response["channel_disabled_body"] = dict(CHANNEL_DISABLED_BODY)
	exc = frappe.PermissionError(CHANNEL_DISABLED_MESSAGE)
	exc.http_status_code = 403  # type: ignore[attr-defined]
	raise exc


def require_canal_externo_habilitado() -> None:
	"""Fail closed si el canal guest está apagado o ausente."""
	enabled = cint(
		frappe.db.get_single_value("Club Settings", "espacios_reserva_externa_habilitada") or 0
	)
	if not enabled:
		raise_channel_disabled()


def require_sesion_externa(sesion_token: str | None) -> None:
	require_canal_externo_habilitado()
	if not verify_sesion_token(sesion_token):
		_deny()


def resolve_monto_arancel_externo(espacio: str | None = None) -> float:
	"""Tarifa canal externo: `tarifa_externo` o standard_rate del ítem ALQ."""
	if espacio and frappe.db.exists("Espacio", espacio):
		tarifa = flt(frappe.db.get_value("Espacio", espacio, "tarifa_externo") or 0)
		if tarifa > 0:
			return tarifa
	if not frappe.db.exists("Item", ITEM_ALQUILER_EXTERNO):
		frappe.throw(
			_("No hay ítem de alquiler configurado ({0})").format(ITEM_ALQUILER_EXTERNO),
			frappe.ValidationError,
		)
	rate = flt(frappe.db.get_value("Item", ITEM_ALQUILER_EXTERNO, "standard_rate") or 0)
	if rate <= 0:
		frappe.throw(_("La tarifa de alquiler debe ser mayor a cero"), frappe.ValidationError)
	return rate


def abrir_sesion_reserva_externa() -> dict[str, Any]:
	"""Emite `sesion_token` HMAC (~2 h) si el canal está habilitado."""
	require_canal_externo_habilitado()
	return {"sesion_token": sign_sesion_token()}


def get_espacios_disponibles_externo(
	*,
	sesion_token: str,
	fecha: str | Any,
	tipo_espacio: str | None = None,
) -> dict[str, Any]:
	"""Grilla 08–22 con monto de tarifa externa."""
	require_sesion_externa(sesion_token)
	target = getdate(fecha)
	filters: dict[str, Any] = {"alquilable": 1, "habilitado": 1}
	if tipo_espacio:
		filters["tipo"] = tipo_espacio

	espacios = frappe.get_all(
		"Espacio",
		filters=filters,
		fields=[
			"name",
			"titulo",
			"tipo",
			"capacidad_personas",
			"tarifa_externo",
			"imagen",
			"imagen_portal",
		],
		order_by="titulo asc",
		limit=0,
	)
	result: list[dict[str, Any]] = []
	for esp in espacios:
		occupancy = get_occupancy(esp.name, target)
		slots: list[dict[str, Any]] = []
		cur = SLOT_INICIO_MINUTOS
		while cur + SLOT_DURACION_MINUTOS <= SLOT_FIN_MINUTOS:
			end = cur + SLOT_DURACION_MINUTOS
			ocupado = _slot_is_occupied(occupancy, cur, end)
			slots.append(
				{
					"hora_inicio": _format_minutes(cur),
					"hora_fin": _format_minutes(end),
					"estado": "ocupado" if ocupado else "libre",
				}
			)
			cur = end
		result.append(
			{
				"espacio": esp.name,
				"titulo": esp.titulo or esp.name,
				"tipo": esp.tipo,
				"capacidad_personas": esp.capacidad_personas,
				"monto_arancel": resolve_monto_arancel_externo(esp.name),
				"imagen": _imagen_espacio(esp),
				"combo_con": _combo_con(esp.name),
				"slots": slots,
			}
		)
	return {"fecha": str(target), "espacios": result}


def solicitar_reserva_externa(
	*,
	sesion_token: str,
	espacio: str,
	fecha: str | Any,
	hora_inicio: str | Any,
	hora_fin: str | Any,
	arrendatario_nombre: str,
	arrendatario_contacto: str,
) -> dict[str, Any]:
	"""Crea Alquiler externo Temporal Pendiente con token_acceso."""
	require_sesion_externa(sesion_token)

	nombre = (arrendatario_nombre or "").strip()
	contacto = (arrendatario_contacto or "").strip()
	if not nombre or not contacto:
		frappe.throw(
			_("Indicá nombre y contacto del arrendatario"),
			frappe.ValidationError,
		)

	espacio_name = (espacio or "").strip()
	if not espacio_name or not frappe.db.exists("Espacio", espacio_name):
		frappe.throw(_("Espacio inválido"), frappe.ValidationError)

	esp = frappe.db.get_value(
		"Espacio",
		espacio_name,
		["alquilable", "habilitado", "titulo"],
		as_dict=True,
	)
	if not esp or not esp.alquilable or not esp.habilitado:
		frappe.throw(
			_("El espacio {0} no está disponible para reserva").format(espacio_name),
			frappe.ValidationError,
		)

	target = getdate(fecha)
	hora_desde = _as_hhmmss(hora_inicio)
	hora_hasta = _as_hhmmss(hora_fin)
	validate_time_range(hora_desde, hora_hasta)

	assert_no_overlap_with_occupancy(espacio_name, target, hora_desde, hora_hasta)
	conflicts = find_occupancy_conflicts(espacio_name, target, hora_desde, hora_hasta)
	if conflicts:
		frappe.throw(
			_("El horario se solapa con ocupación existente del espacio {0}").format(
				espacio_name
			),
			frappe.ValidationError,
		)

	monto = resolve_monto_arancel_externo(espacio_name)
	token = generate_token_acceso()
	# Garantizar unicidad ante colisión teórica
	while frappe.db.exists(RESERVA_DOCTYPE, {"token_acceso": token}):
		token = generate_token_acceso()

	doc = frappe.get_doc(
		{
			"doctype": RESERVA_DOCTYPE,
			"espacio": espacio_name,
			"tipo": "Alquiler externo",
			"modalidad_alquiler": "Temporal",
			"estado": "Pendiente",
			"fecha": target,
			"hora_desde": hora_desde,
			"hora_hasta": hora_hasta,
			"arrendatario_nombre": nombre,
			"arrendatario_contacto": contacto,
			"monto_arancel": monto,
			"item_alquiler": ITEM_ALQUILER_EXTERNO
			if frappe.db.exists("Item", ITEM_ALQUILER_EXTERNO)
			else None,
			"token_acceso": token,
			"motivo": _("Reserva externa online"),
		}
	)
	doc.insert(ignore_permissions=True)

	return {
		"status": "ok",
		"reserva": doc.name,
		"token_acceso": token,
		"espacio": espacio_name,
		"fecha": str(target),
		"hora_inicio": hora_desde,
		"hora_fin": hora_hasta,
		"estado": doc.estado,
		"monto_arancel": flt(doc.monto_arancel),
	}


def _get_reserva_by_token(token_acceso: str) -> frappe.model.document.Document:
	"""Lookup por token; fail closed genérico (sin filtrar existencia)."""
	require_canal_externo_habilitado()
	token = (token_acceso or "").strip()
	if not token:
		_deny()
	name = frappe.db.get_value(
		RESERVA_DOCTYPE,
		{"token_acceso": token, "tipo": "Alquiler externo"},
		"name",
	)
	if not name:
		_deny()
	return frappe.get_doc(RESERVA_DOCTYPE, name)


def get_reserva_externa(token_acceso: str) -> dict[str, Any]:
	"""Detalle acotado de la reserva externa por token_acceso."""
	doc = _get_reserva_by_token(token_acceso)
	return {
		"reserva": doc.name,
		"espacio": doc.espacio,
		"fecha": str(doc.fecha) if doc.fecha else None,
		"hora_inicio": _as_hhmmss(doc.hora_desde) if doc.hora_desde else None,
		"hora_fin": _as_hhmmss(doc.hora_hasta) if doc.hora_hasta else None,
		"estado": doc.estado,
		"monto_arancel": flt(doc.monto_arancel),
		"comprobante": doc.comprobante,
		"fecha_comprobante": str(doc.fecha_comprobante) if doc.fecha_comprobante else None,
		"arrendatario_nombre": doc.arrendatario_nombre,
		"motivo_rechazo": doc.motivo_rechazo,
	}


def adjuntar_comprobante_externo(*, token_acceso: str, file_url: str) -> dict[str, Any]:
	"""Adjunta PDF a reserva externa Pendiente vía token_acceso."""
	doc = _get_reserva_by_token(token_acceso)
	if doc.estado != "Pendiente":
		frappe.throw(
			_("La reserva debe estar Pendiente (actual: {0})").format(doc.estado),
			frappe.ValidationError,
		)

	url = (file_url or "").strip()
	if not url:
		frappe.throw(_("Indique el archivo del comprobante"), frappe.ValidationError)
	if not _is_pdf_file(url):
		frappe.throw(_("El comprobante debe ser un PDF"), frappe.ValidationError)

	doc.comprobante = url
	doc.fecha_comprobante = now_datetime()
	doc.save(ignore_permissions=True)

	return {
		"status": "ok",
		"reserva": doc.name,
		"estado": doc.estado,
		"comprobante": doc.comprobante,
		"fecha_comprobante": str(doc.fecha_comprobante) if doc.fecha_comprobante else None,
	}


def upload_y_adjuntar_comprobante_externo(
	*,
	token_acceso: str,
	filename: str,
	content_b64: str,
) -> dict[str, Any]:
	"""Guest: sube PDF (base64) vinculado a la reserva y lo adjunta como comprobante."""
	import base64

	from frappe.utils.file_manager import save_file

	doc = _get_reserva_by_token(token_acceso)
	if doc.estado != "Pendiente":
		frappe.throw(
			_("La reserva debe estar Pendiente (actual: {0})").format(doc.estado),
			frappe.ValidationError,
		)

	fname = (filename or "").strip() or "comprobante.pdf"
	if not fname.lower().endswith(".pdf"):
		frappe.throw(_("El comprobante debe ser un PDF"), frappe.ValidationError)

	raw = (content_b64 or "").strip()
	if not raw:
		frappe.throw(_("Indique el archivo del comprobante"), frappe.ValidationError)
	try:
		# data URL opcional
		if "," in raw and raw.lower().startswith("data:"):
			raw = raw.split(",", 1)[1]
		content = base64.b64decode(raw, validate=False)
	except Exception:
		frappe.throw(_("Archivo inválido"), frappe.ValidationError)

	if not content:
		frappe.throw(_("Archivo vacío"), frappe.ValidationError)
	if len(content) > 10 * 1024 * 1024:
		frappe.throw(_("El archivo supera 10 MB"), frappe.ValidationError)
	# magic %PDF
	if not content.startswith(b"%PDF"):
		frappe.throw(_("El comprobante debe ser un PDF"), frappe.ValidationError)

	file_doc = save_file(
		fname,
		content,
		RESERVA_DOCTYPE,
		doc.name,
		is_private=1,
	)
	return adjuntar_comprobante_externo(
		token_acceso=token_acceso,
		file_url=file_doc.file_url,
	)
