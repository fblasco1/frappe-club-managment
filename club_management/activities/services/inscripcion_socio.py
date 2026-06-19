"""Inscripción de socios a actividades (post-pago y resumen en Socio)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, today

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
	ensure_actividad_exists,
)
from club_management.members.services.socio_transitions import cambiar_estado

INSCRIPCION_DOCTYPE = "Inscripcion Actividad"
SOCIO_DOCTYPE = "Socio"


def _format_inscripcion_label(row: dict[str, Any]) -> str:
	actividad = row.get("actividad") or ""
	grupo = row.get("grupo_actividad") or ""
	equipo = row.get("equipo_actividad") or ""
	if not grupo:
		return actividad
	grupo_titulo = grupo.split(" / ")[-1] if " / " in grupo else grupo
	label = f"{actividad} ({grupo_titulo}"
	if equipo:
		equipo_titulo = equipo.split(" / ")[-1] if " / " in equipo else equipo
		label += f" — {equipo_titulo}"
	label += ")"
	return label


def actividades_resumen_socio(socio_name: str) -> str:
	"""Resumen legible de inscripciones activas."""
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa"},
		fields=["actividad", "grupo_actividad", "equipo_actividad"],
		order_by="actividad asc, grupo_actividad asc",
	)
	if not rows:
		return ""
	return ", ".join(_format_inscripcion_label(row) for row in rows)


def sync_socio_actividad_resumen(socio_name: str) -> None:
	frappe.db.set_value(
		SOCIO_DOCTYPE,
		socio_name,
		"actividad",
		actividades_resumen_socio(socio_name),
		update_modified=False,
	)


def resolve_item_arancel_inscripcion(inscripcion_name: str) -> str | None:
	"""Ítem de cobro: grupo → actividad."""
	row = frappe.db.get_value(
		INSCRIPCION_DOCTYPE,
		inscripcion_name,
		["grupo_actividad", "actividad"],
		as_dict=True,
	)
	if not row:
		return None
	if row.grupo_actividad:
		item = frappe.db.get_value("Grupo Actividad", row.grupo_actividad, "item")
		if item:
			return item
	return frappe.db.get_value("Actividad", row.actividad, "item")


def resolve_monto_arancel_inscripcion(inscripcion_name: str) -> tuple[str | None, float]:
	"""Devuelve `(item_code, monto)` del arancel de la inscripción."""
	item_code = resolve_item_arancel_inscripcion(inscripcion_name)
	if not item_code:
		return None, 0.0
	monto = flt(
		frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate")
		or frappe.db.get_value("Item", item_code, "standard_rate")
		or 0
	)
	return item_code, monto


def list_inscripciones_socio(
	socio_name: str,
	*,
	incluir_bajas: bool = False,
) -> list[dict[str, Any]]:
	"""Filas de inscripciones del socio para Desk."""
	filters: dict[str, Any] = {"socio": socio_name}
	if not incluir_bajas:
		filters["estado"] = "Activa"

	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
			"estado",
			"fecha_inscripcion",
		],
		order_by="fecha_inscripcion desc, name asc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		item_code, monto = resolve_monto_arancel_inscripcion(row.name)
		result.append(
			{
				"name": row.name,
				"actividad": row.actividad,
				"grupo_actividad": row.grupo_actividad,
				"equipo_actividad": row.equipo_actividad,
				"estado": row.estado,
				"fecha_inscripcion": row.fecha_inscripcion,
				"item_arancel": item_code,
				"monto": monto,
			}
		)
	return result


def list_inscripciones_socio_desk(
	socio_name: str,
	*,
	incluir_bajas: bool = False,
) -> list[dict[str, Any]]:
	"""Lista inscripciones del socio (Secretaría)."""
	from club_management.members.services.socio_operaciones_secretaria import (
		ensure_secretaria_operacion_access,
	)

	ensure_secretaria_operacion_access()
	if not frappe.db.exists(SOCIO_DOCTYPE, socio_name):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	return list_inscripciones_socio(socio_name, incluir_bajas=incluir_bajas)


def baja_inscripcion_desk(
	inscripcion_name: str,
	*,
	motivo: str | None = None,
) -> dict[str, Any]:
	"""Da de baja una inscripción activa sin cambiar el estado global del socio."""
	from club_management.members.services.socio_operaciones_secretaria import (
		ensure_secretaria_operacion_access,
	)

	ensure_secretaria_operacion_access()
	if not frappe.db.exists(INSCRIPCION_DOCTYPE, inscripcion_name):
		frappe.throw(_("Inscripción no encontrada"), frappe.DoesNotExistError)

	doc = frappe.get_doc(INSCRIPCION_DOCTYPE, inscripcion_name)
	if doc.estado != "Activa":
		frappe.throw(
			_("Solo se puede dar de baja una inscripción activa."),
			frappe.ValidationError,
		)

	socio_name = doc.socio
	doc.estado = "Baja"
	doc.save(ignore_permissions=True)
	sync_socio_actividad_resumen(socio_name)

	return {
		"status": "ok",
		"inscripcion": inscripcion_name,
		"socio": socio_name,
		"motivo": (motivo or "").strip() or None,
		"actividad_resumen": actividades_resumen_socio(socio_name),
		"estado_socio": frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado"),
	}


def _resolve_grupo_actividad(actividad: str, grupo_key: str | None) -> str | None:
	if not grupo_key:
		return None
	if frappe.db.exists("Grupo Actividad", grupo_key):
		name = grupo_key
	else:
		name = frappe.db.get_value(
			"Grupo Actividad",
			{"actividad": actividad, "titulo": grupo_key},
			"name",
		)
	if not name:
		return None
	if not frappe.db.get_value("Grupo Actividad", name, "habilitada"):
		return None
	return name


def _resolve_equipo_actividad(grupo: str, equipo_key: str | None) -> str | None:
	if not equipo_key:
		return None
	if frappe.db.exists("Equipo Actividad", equipo_key):
		name = equipo_key
	else:
		name = frappe.db.get_value(
			"Equipo Actividad",
			{"grupo_actividad": grupo, "titulo": equipo_key},
			"name",
		)
	if not name:
		return None
	if frappe.db.get_value("Equipo Actividad", name, "grupo_actividad") != grupo:
		return None
	if not frappe.db.get_value("Equipo Actividad", name, "habilitada"):
		return None
	return name


def inscribir_socio_selecciones(
	socio_name: str,
	selecciones: list[dict[str, Any]],
	*,
	activar: bool = True,
) -> list[str]:
	"""Crea inscripciones desde selecciones `{actividad, grupo?, equipo?}`."""
	labels: list[str] = []
	for sel in selecciones:
		actividad_key = (sel.get("actividad") or "").strip()
		if not actividad_key:
			continue
		actividad_name = ensure_actividad_exists(actividad_key)
		if not actividad_name:
			continue

		grupo_key = (sel.get("grupo") or sel.get("grupo_actividad") or "").strip() or None
		grupo_name = _resolve_grupo_actividad(actividad_name, grupo_key)
		if grupo_key and not grupo_name and frappe.db.exists("Grupo Actividad", grupo_key):
			grupo_name = grupo_key
		equipo_name = None
		equipo_key = (sel.get("equipo") or sel.get("equipo_actividad") or "").strip() or None
		equipo_name = None
		if grupo_name:
			equipo_name = _resolve_equipo_actividad(grupo_name, equipo_key)
			if equipo_key and not equipo_name and frappe.db.exists("Equipo Actividad", equipo_key):
				equipo_name = equipo_key

		dup_filters: dict[str, Any] = {
			"socio": socio_name,
			"estado": "Activa",
			"actividad": actividad_name,
		}
		if grupo_name:
			dup_filters["grupo_actividad"] = grupo_name
			if equipo_name:
				dup_filters["equipo_actividad"] = equipo_name
		else:
			dup_filters["grupo_actividad"] = ["is", "not set"]

		if frappe.db.exists(INSCRIPCION_DOCTYPE, dup_filters):
			labels.append(_format_inscripcion_label(
				{
					"actividad": actividad_name,
					"grupo_actividad": grupo_name,
					"equipo_actividad": equipo_name,
				}
			))
			continue

		actividad_inscripcion = (
			frappe.db.get_value("Grupo Actividad", grupo_name, "actividad") if grupo_name else actividad_name
		)
		doc = frappe.get_doc(
			{
				"doctype": INSCRIPCION_DOCTYPE,
				"socio": socio_name,
				"actividad": actividad_inscripcion,
				"grupo_actividad": grupo_name,
				"equipo_actividad": equipo_name,
				"estado": "Activa",
				"fecha_inscripcion": today(),
			}
		)
		doc.insert(ignore_permissions=True)
		labels.append(_format_inscripcion_label(
			{
				"actividad": actividad_name,
				"grupo_actividad": grupo_name,
				"equipo_actividad": equipo_name,
			}
		))

	sync_socio_actividad_resumen(socio_name)
	if activar:
		cambiar_estado(
			socio_name,
			"Activo",
			motivo="Inscripción de actividades post-pago",
		)
	return labels


def inscribir_socio_actividades(
	socio_name: str,
	actividad_keys: list[str],
	*,
	activar: bool = True,
) -> list[str]:
	"""Compat: lista simple de actividades (sin grupo)."""
	selecciones = [{"actividad": key} for key in actividad_keys]
	return inscribir_socio_selecciones(socio_name, selecciones, activar=activar)


def inscribir_actividades_desk(
	socio_name: str,
	selecciones: list[dict[str, Any]],
) -> dict[str, Any]:
	"""Inscripción manual desde Desk (Secretaría). Activa si estaba pendiente."""
	from club_management.members.services.socio_operaciones_secretaria import (
		ensure_secretaria_operacion_access,
	)

	ensure_secretaria_operacion_access()
	if not selecciones:
		frappe.throw(_("Seleccione al menos una actividad."), frappe.ValidationError)

	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	activar = estado == ESTADO_SOCIO_PENDIENTE_INSCRIPCION
	inscritas = inscribir_socio_selecciones(socio_name, selecciones, activar=activar)
	return {
		"status": "ok",
		"socio": socio_name,
		"actividades": inscritas,
		"actividad_resumen": actividades_resumen_socio(socio_name),
		"estado": frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado"),
	}


def confirmar_inscripcion_post_pago(
	solicitud_name: str,
	actividad_keys: list[str] | None = None,
	*,
	selecciones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if not solicitud.socio_generado:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	socio = frappe.get_doc(SOCIO_DOCTYPE, solicitud.socio_generado)
	if socio.estado != ESTADO_SOCIO_PENDIENTE_INSCRIPCION:
		frappe.throw(
			_("La inscripción de actividades no está disponible para este socio."),
			frappe.ValidationError,
		)

	if selecciones is not None:
		payload = selecciones
	elif actividad_keys is not None:
		payload = [{"actividad": key} for key in actividad_keys]
	else:
		payload = []

	inscritas = inscribir_socio_selecciones(socio.name, payload, activar=True)
	return {
		"status": "ok",
		"socio": socio.name,
		"actividades": inscritas,
		"actividad_resumen": actividades_resumen_socio(socio.name),
	}
