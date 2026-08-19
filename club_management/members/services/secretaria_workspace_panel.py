"""Listas preview del workspace Secretaría (Desk)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import fmt_money, formatdate

from club_management.members.services.secretaria_panel_kpis import get_panel_metricas_payload
from club_management.finance.services.recordatorio_sueldos import (
	get_recordatorio_provision_sueldos_payload,
)

LIST_LIMIT = 5

SOLICITUD_DOCTYPE = "Solicitud Asociacion"
SOLICITUD_ESTADOS_PENDIENTES = ("Pendiente", "Requiere Corrección")
SOCIO_DOCTYPE = "Socio"
INSCRIPCION_DOCTYPE = "Inscripcion Actividad"


def get_solicitudes_pendientes_preview(*, limit: int = LIST_LIMIT) -> list[dict[str, Any]]:
	"""Solicitudes pendientes de revisión o corrección del socio (máx. `limit`)."""
	limit = max(1, min(int(limit), LIST_LIMIT))
	rows = frappe.get_all(
		SOLICITUD_DOCTYPE,
		filters={"workflow_state": ["in", list(SOLICITUD_ESTADOS_PENDIENTES)]},
		fields=["name", "nombre", "apellido", "dni", "creation", "workflow_state"],
		order_by="creation asc",
		limit=limit,
	)
	return [_format_solicitud_row(row) for row in rows]


def get_socios_morosos_preview(*, limit: int = LIST_LIMIT) -> list[dict[str, Any]]:
	"""Socios `Moroso` ordenados por mayor `saldo_deuda` (máx. `limit`)."""
	limit = max(1, min(int(limit), LIST_LIMIT))
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": "Moroso"},
		fields=[
			"name",
			"nombre",
			"apellido",
			"categoria",
			"estado",
			"actividad",
			"solicitud_origen",
			"saldo_deuda",
		],
		order_by="saldo_deuda desc, modified desc",
		limit=limit,
	)
	return [_format_socio_moroso_row(row) for row in rows]


CUOTAS_CATEGORIAS = (
	"Activo",
	"Menor",
	"2° Hermano",
	"3° Hermano",
	"Adherente",
	"Jubilado",
)


def get_cuotas_sociales_payload() -> dict[str, Any]:
	"""Cuotas sociales por categoría desde Club Settings."""
	settings = frappe.get_single("Club Settings")
	rows = []
	by_categoria = {row.categoria: row for row in (settings.cuotas_categoria or [])}
	for categoria in CUOTAS_CATEGORIAS:
		row = by_categoria.get(categoria)
		rows.append(
			{
				"categoria": categoria,
				"monto": float(row.monto) if row else 0.0,
				"item": (row.item if row else None) or settings.item_cuota_social or "",
			}
		)
	return {
		"item_cuota_social_default": settings.item_cuota_social or "",
		"cuotas": rows,
		"vigente_desde": str(getattr(settings, "cuotas_vigente_desde", None) or ""),
	}


def save_cuotas_sociales_payload(
	rows: list[dict[str, Any]],
	vigente_desde: str | None = None,
) -> dict[str, Any]:
	"""Persiste montos de cuotas sociales en Club Settings."""
	settings = frappe.get_single("Club Settings")
	allowed = set(CUOTAS_CATEGORIAS)
	incoming = {row.get("categoria"): row for row in rows if row.get("categoria") in allowed}

	for categoria in CUOTAS_CATEGORIAS:
		data = incoming.get(categoria)
		if not data:
			continue
		monto = float(data.get("monto") or 0)
		if monto <= 0:
			frappe.throw(frappe._("El monto de {0} debe ser mayor a cero.").format(categoria))
		item = (data.get("item") or "").strip() or settings.item_cuota_social
		existing = next(
			(row for row in (settings.cuotas_categoria or []) if row.categoria == categoria),
			None,
		)
		if existing:
			existing.monto = monto
			if item:
				existing.item = item
		else:
			settings.append(
				"cuotas_categoria",
				{"categoria": categoria, "monto": monto, "item": item},
			)

	if vigente_desde is not None:
		settings.cuotas_vigente_desde = vigente_desde or None

	settings.save()

	from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_erpnext

	sync_cuotas_sociales_erpnext()
	return get_cuotas_sociales_payload()


def get_panel_lists_payload(
	*,
	reference_date: str | None = None,
	tendencia_reference_date: str | None = None,
) -> dict[str, Any]:
	"""Payload completo para el panel (métricas + solicitudes)."""
	return {
		"metricas": get_panel_metricas_payload(
			reference_date=reference_date,
			tendencia_reference_date=tendencia_reference_date,
		),
		"solicitudes_pendientes": get_solicitudes_pendientes_preview(),
		"recordatorio_sueldos": get_recordatorio_provision_sueldos_payload(
			reference_date=reference_date
		),
	}


def _format_solicitud_row(row: dict[str, Any]) -> dict[str, Any]:
	nombre = (row.get("nombre") or "").strip()
	apellido = (row.get("apellido") or "").strip()
	titulo = " ".join(part for part in (nombre, apellido) if part) or row["name"]
	creation = row.get("creation")
	estado = row.get("workflow_state") or ""
	return {
		"name": row["name"],
		"titulo": titulo,
		"dni": row.get("dni") or "",
		"creation": creation,
		"fecha_label": formatdate(creation) if creation else "",
		"estado": estado,
		"estado_label": estado or "—",
	}


def _resolve_socio_actividad(row: dict[str, Any]) -> str:
	"""Resumen de inscripciones, campo Socio o interés declarado en la solicitud."""
	from club_management.activities.services.inscripcion_socio import actividades_resumen_socio

	if row.get("name") and frappe.db.table_exists(INSCRIPCION_DOCTYPE):
		resumen = actividades_resumen_socio(row["name"])
		if resumen:
			return resumen

	actividad = (row.get("actividad") or "").strip()
	if actividad:
		return actividad
	origen = row.get("solicitud_origen")
	if not origen:
		return ""
	return (frappe.db.get_value("Solicitud Asociacion", origen, "actividad_interes") or "").strip()


def _format_socio_moroso_row(row: dict[str, Any]) -> dict[str, Any]:
	nombre = (row.get("nombre") or "").strip()
	apellido = (row.get("apellido") or "").strip()
	nombre_apellido = " ".join(part for part in (nombre, apellido) if part) or row["name"]
	saldo = float(row.get("saldo_deuda") or 0)
	actividad = _resolve_socio_actividad(row)
	return {
		"name": row["name"],
		"identificador": row["name"],
		"nombre_apellido": nombre_apellido,
		"categoria": row.get("categoria") or "",
		"estado": row.get("estado") or "",
		"actividad": actividad,
		"actividad_label": actividad or "—",
		"saldo_deuda": saldo,
		"saldo_deuda_label": fmt_money(saldo),
	}
