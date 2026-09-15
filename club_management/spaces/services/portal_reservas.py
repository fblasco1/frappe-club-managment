"""Servicio de reservas de espacios para el portal del socio (SP-3 / SP-7)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_time, getdate

from club_management.members.services.portal_session import get_current_socio
from club_management.spaces.availability import (
	assert_no_overlap_with_occupancy,
	find_occupancy_conflicts,
	get_occupancy,
	validate_time_range,
)

ITEM_ALQUILER_SOCIO = "ICDPE-ALQ-ARS-TEMP"
SLOT_INICIO_MINUTOS = 8 * 60  # 08:00
SLOT_FIN_MINUTOS = 22 * 60  # 22:00
SLOT_DURACION_MINUTOS = 60


def _require_active_socio() -> frappe.model.document.Document:
	socio = get_current_socio()
	if socio.estado != "Activo":
		frappe.throw(_("Solo un socio Activo puede reservar espacios"), frappe.ValidationError)
	return socio


def _as_hhmmss(value: Any) -> str:
	t = get_time(value)
	return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"


def _minutes(value: Any) -> int:
	t = get_time(value)
	return t.hour * 60 + t.minute


def _format_minutes(total: int) -> str:
	hours, minutes = divmod(total, 60)
	return f"{hours:02d}:{minutes:02d}:00"


def resolve_monto_arancel_socio(espacio: str | None = None) -> float:
	"""Tarifa portal: `tarifa_socio` del espacio, o standard_rate del ítem ALQ."""
	if espacio and frappe.db.exists("Espacio", espacio):
		tarifa = flt(frappe.db.get_value("Espacio", espacio, "tarifa_socio") or 0)
		if tarifa > 0:
			return tarifa
	if not frappe.db.exists("Item", ITEM_ALQUILER_SOCIO):
		frappe.throw(
			_("No hay ítem de alquiler configurado ({0})").format(ITEM_ALQUILER_SOCIO),
			frappe.ValidationError,
		)
	rate = flt(frappe.db.get_value("Item", ITEM_ALQUILER_SOCIO, "standard_rate") or 0)
	if rate <= 0:
		frappe.throw(_("La tarifa de alquiler debe ser mayor a cero"), frappe.ValidationError)
	return rate


def _slot_is_occupied(occupancy: list[dict[str, Any]], start_min: int, end_min: int) -> bool:
	for slot in occupancy:
		s0 = _minutes(slot["hora_desde"])
		s1 = _minutes(slot["hora_hasta"])
		if s1 <= s0:
			s1 += 24 * 60
		if start_min < s1 and s0 < end_min:
			return True
	return False


def _imagen_espacio(esp: dict[str, Any]) -> str | None:
	imagen = (esp.get("imagen") or "").strip()
	if imagen:
		return imagen
	portal = (esp.get("imagen_portal") or "").strip()
	return portal or None


def _combo_con(espacio_name: str) -> list[dict[str, str]]:
	rows = frappe.get_all(
		"Espacio Combo",
		filters={"parent": espacio_name, "parenttype": "Espacio"},
		fields=["espacio"],
		order_by="idx asc",
	)
	out: list[dict[str, str]] = []
	for row in rows:
		name = (row.espacio or "").strip()
		if not name or not frappe.db.exists("Espacio", name):
			continue
		titulo = frappe.db.get_value("Espacio", name, "titulo") or name
		out.append({"espacio": name, "titulo": str(titulo)})
	return out


def get_espacios_disponibles(
	fecha: str | Any,
	tipo_espacio: str | None = None,
) -> dict[str, Any]:
	"""Grilla horaria de espacios alquilables: slots libres / ocupados."""
	_require_active_socio()
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
			"tarifa_socio",
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
		monto = resolve_monto_arancel_socio(esp.name)
		result.append(
			{
				"espacio": esp.name,
				"titulo": esp.titulo or esp.name,
				"tipo": esp.tipo,
				"capacidad_personas": esp.capacidad_personas,
				"monto_arancel": monto,
				"imagen": _imagen_espacio(esp),
				"combo_con": _combo_con(esp.name),
				"slots": slots,
			}
		)
	return {"fecha": str(target), "espacios": result}


def _create_cargo_borrador(*, socio: str, monto: float, reserva_label: str) -> str:
	"""Crea Cargo Socio Pendiente sin auto-facturar."""
	if not frappe.db.exists("Item", ITEM_ALQUILER_SOCIO):
		frappe.throw(
			_("No hay ítem de alquiler configurado ({0})").format(ITEM_ALQUILER_SOCIO),
			frappe.ValidationError,
		)
	frappe.flags.skip_cargo_auto_invoice = True
	try:
		cargo = frappe.get_doc(
			{
				"doctype": "Cargo Socio",
				"socio": socio,
				"titulo": _("Alquiler espacio: {0}").format(reserva_label),
				"tipo_cargo": "Otro",
				"modo_cobro": "Unico",
				"item": ITEM_ALQUILER_SOCIO,
				"monto": monto,
				"fecha_desde": getdate(),
				"estado": "Pendiente",
				"observaciones": _("Borrador generado por reserva portal"),
			}
		)
		cargo.insert(ignore_permissions=True)
		return cargo.name
	finally:
		frappe.flags.skip_cargo_auto_invoice = False


def solicitar_reserva_espacio(
	espacio: str,
	fecha: str | Any,
	hora_inicio: str | Any,
	hora_fin: str | Any,
	espacios_extra: list[str] | str | None = None,
) -> dict[str, Any]:
	"""Bloquea el slot (Pendiente), vincula al socio de sesión y genera cargo borrador.

	`espacios_extra`: otros espacios en el mismo horario (reserva conjunta).
	"""
	socio = _require_active_socio()
	extra_raw = espacios_extra
	if isinstance(extra_raw, str):
		extra_raw = frappe.parse_json(extra_raw) if extra_raw.strip().startswith("[") else [
			p.strip() for p in extra_raw.split(",") if p.strip()
		]
	extras = [str(x).strip() for x in (extra_raw or []) if str(x).strip()]
	espacios = [espacio.strip()] + [e for e in extras if e and e != espacio.strip()]
	# dedupe preserving order
	seen: set[str] = set()
	ordered: list[str] = []
	for name in espacios:
		if name in seen:
			continue
		seen.add(name)
		ordered.append(name)

	target = getdate(fecha)
	hora_desde = _as_hhmmss(hora_inicio)
	hora_hasta = _as_hhmmss(hora_fin)
	validate_time_range(hora_desde, hora_hasta)

	creadas: list[dict[str, Any]] = []
	for espacio_name in ordered:
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

		assert_no_overlap_with_occupancy(espacio_name, target, hora_desde, hora_hasta)
		conflicts = find_occupancy_conflicts(espacio_name, target, hora_desde, hora_hasta)
		if conflicts:
			frappe.throw(
				_("El horario se solapa con ocupación existente del espacio {0}").format(
					espacio_name
				),
				frappe.ValidationError,
			)

		monto = resolve_monto_arancel_socio(espacio_name)
		label = f"{esp.titulo or espacio_name} {target} {hora_desde[:5]}-{hora_hasta[:5]}"
		cargo_name = _create_cargo_borrador(socio=socio.name, monto=monto, reserva_label=label)

		doc = frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio_name,
				"tipo": "Alquiler socio",
				"estado": "Pendiente",
				"fecha": target,
				"hora_desde": hora_desde,
				"hora_hasta": hora_hasta,
				"socio": socio.name,
				"monto_arancel": monto,
				"cargo_socio": cargo_name,
				"motivo": _("Reserva portal socio"),
			}
		)
		doc.insert(ignore_permissions=True)
		creadas.append(
			{
				"reserva": doc.name,
				"espacio": espacio_name,
				"estado": doc.estado,
				"monto_arancel": flt(doc.monto_arancel),
				"cargo_socio": cargo_name,
			}
		)

	primera = creadas[0]
	return {
		"status": "ok",
		"reserva": primera["reserva"],
		"estado": primera["estado"],
		"socio": socio.name,
		"espacio": primera["espacio"],
		"fecha": str(target),
		"hora_inicio": hora_desde,
		"hora_fin": hora_hasta,
		"monto_arancel": flt(sum(c["monto_arancel"] for c in creadas)),
		"cargo_socio": primera["cargo_socio"],
		"reservas": creadas,
	}


def list_reservas_propias() -> list[dict[str, Any]]:
	"""Reservas del socio de sesión (aislamiento)."""
	socio = get_current_socio()
	rows = frappe.get_all(
		"Reserva Espacio",
		filters={"socio": socio.name, "tipo": "Alquiler socio"},
		fields=[
			"name",
			"espacio",
			"fecha",
			"hora_desde",
			"hora_hasta",
			"estado",
			"monto_arancel",
			"cargo_socio",
			"comprobante",
			"fecha_comprobante",
			"motivo_rechazo",
		],
		order_by="fecha desc, hora_desde desc",
		limit=0,
	)
	out: list[dict[str, Any]] = []
	for row in rows:
		out.append(
			{
				"name": row.name,
				"espacio": row.espacio,
				"fecha": str(row.fecha) if row.fecha else None,
				"hora_inicio": _as_hhmmss(row.hora_desde) if row.hora_desde else None,
				"hora_fin": _as_hhmmss(row.hora_hasta) if row.hora_hasta else None,
				"estado": row.estado,
				"monto_arancel": flt(row.monto_arancel),
				"cargo_socio": row.cargo_socio,
				"comprobante": row.comprobante,
				"fecha_comprobante": str(row.fecha_comprobante) if row.fecha_comprobante else None,
				"motivo_rechazo": row.motivo_rechazo,
			}
		)
	return out


def get_reserva_propia(reserva: str) -> dict[str, Any]:
	"""Lectura de una reserva propia; fail closed si es ajena."""
	socio = get_current_socio()
	name = (reserva or "").strip()
	if not name or not frappe.db.exists("Reserva Espacio", name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doc = frappe.get_doc("Reserva Espacio", name)
	if doc.socio != socio.name or doc.tipo != "Alquiler socio":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return {
		"name": doc.name,
		"espacio": doc.espacio,
		"fecha": str(doc.fecha) if doc.fecha else None,
		"hora_inicio": _as_hhmmss(doc.hora_desde),
		"hora_fin": _as_hhmmss(doc.hora_hasta),
		"estado": doc.estado,
		"monto_arancel": flt(doc.monto_arancel),
		"cargo_socio": doc.cargo_socio,
		"comprobante": doc.comprobante,
		"fecha_comprobante": str(doc.fecha_comprobante) if doc.fecha_comprobante else None,
		"motivo_rechazo": doc.motivo_rechazo,
	}
