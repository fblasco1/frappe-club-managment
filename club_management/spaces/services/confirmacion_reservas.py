"""Confirmación Coordinación y comprobante PDF de reservas online.

Spec: `club_management/specs/reservas_espacio_confirmacion.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from club_management.members.services.portal_session import get_current_socio
from club_management.spaces.availability import find_occupancy_conflicts
from club_management.spaces.permissions import ensure_spaces_write_access

RESERVA_DOCTYPE = "Reserva Espacio"
TIPOS_ONLINE = frozenset({"Alquiler socio", "Alquiler externo"})


def _get_reserva(reserva: str) -> frappe.model.document.Document:
	name = (reserva or "").strip()
	if not name or not frappe.db.exists(RESERVA_DOCTYPE, name):
		frappe.throw(_("Reserva no encontrada"), frappe.ValidationError)
	return frappe.get_doc(RESERVA_DOCTYPE, name)


def _assert_pendiente_online(doc: frappe.model.document.Document) -> None:
	if doc.tipo not in TIPOS_ONLINE:
		frappe.throw(_("Solo reservas de alquiler online"), frappe.ValidationError)
	if doc.estado != "Pendiente":
		frappe.throw(
			_("La reserva debe estar Pendiente (actual: {0})").format(doc.estado),
			frappe.ValidationError,
		)


def _is_pdf_file(file_url: str) -> bool:
	url = (file_url or "").strip().lower()
	if not url:
		return False
	if ".pdf" in url.split("?")[0]:
		return True
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "file_name") or ""
	return str(file_name).lower().endswith(".pdf")


def adjuntar_comprobante_reserva(*, reserva: str, file_url: str) -> dict[str, Any]:
	"""Portal: el socio de sesión adjunta PDF a su reserva Pendiente."""
	socio = get_current_socio()
	doc = _get_reserva(reserva)
	if doc.tipo != "Alquiler socio" or doc.socio != socio.name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	_assert_pendiente_online(doc)

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


def list_reservas_pendientes_confirmacion() -> list[dict[str, Any]]:
	"""Cola Desk: reservas Pendiente de alquiler online."""
	ensure_spaces_write_access()
	rows = frappe.get_all(
		RESERVA_DOCTYPE,
		filters={"estado": "Pendiente", "tipo": ["in", list(TIPOS_ONLINE)]},
		fields=[
			"name",
			"espacio",
			"tipo",
			"fecha",
			"hora_desde",
			"hora_hasta",
			"socio",
			"arrendatario_nombre",
			"monto_arancel",
			"comprobante",
			"fecha_comprobante",
			"modified",
		],
		order_by="fecha asc, hora_desde asc",
		limit=0,
	)
	out: list[dict[str, Any]] = []
	for row in rows:
		out.append(
			{
				"name": row.name,
				"espacio": row.espacio,
				"tipo": row.tipo,
				"fecha": str(row.fecha) if row.fecha else None,
				"hora_desde": str(row.hora_desde) if row.hora_desde else None,
				"hora_hasta": str(row.hora_hasta) if row.hora_hasta else None,
				"socio": row.socio,
				"arrendatario_nombre": row.arrendatario_nombre,
				"monto_arancel": row.monto_arancel,
				"comprobante": row.comprobante,
				"fecha_comprobante": str(row.fecha_comprobante) if row.fecha_comprobante else None,
				"modified": str(row.modified) if row.modified else None,
			}
		)
	return out


def confirmar_reserva_espacio(reserva: str) -> dict[str, Any]:
	"""Coordinación: Pendiente → Confirmada; falla si hay conflicto de ocupación."""
	ensure_spaces_write_access()
	doc = _get_reserva(reserva)
	_assert_pendiente_online(doc)

	if doc.fecha and doc.espacio:
		conflicts = find_occupancy_conflicts(
			doc.espacio,
			doc.fecha,
			doc.hora_desde,
			doc.hora_hasta,
			exclude_reserva=doc.name,
		)
		# Solo bloquear si hay ocupación Confirmada / grilla / etc. ajena.
		if conflicts:
			labels = ", ".join(
				f"{c.get('tipo', '?')}:{c.get('ref', '')}" for c in conflicts[:5]
			)
			frappe.throw(
				_("No se puede confirmar: conflicto de ocupación ({0})").format(labels),
				frappe.ValidationError,
			)

	doc.estado = "Confirmada"
	doc.motivo_rechazo = None
	doc.save(ignore_permissions=True)

	return {"status": "ok", "reserva": doc.name, "estado": doc.estado}


def rechazar_reserva_espacio(*, reserva: str, motivo: str) -> dict[str, Any]:
	"""Coordinación: Pendiente → Cancelada; libera slot."""
	ensure_spaces_write_access()
	doc = _get_reserva(reserva)
	_assert_pendiente_online(doc)

	reason = (motivo or "").strip()
	if not reason:
		frappe.throw(_("Indique el motivo del rechazo"), frappe.ValidationError)

	doc.estado = "Cancelada"
	doc.motivo_rechazo = reason
	doc.save(ignore_permissions=True)

	return {
		"status": "ok",
		"reserva": doc.name,
		"estado": doc.estado,
		"motivo_rechazo": doc.motivo_rechazo,
	}
