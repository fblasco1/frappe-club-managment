"""Operaciones Desk de Secretaría sobre el estado del Socio (sin pagos online)."""

from __future__ import annotations

import frappe
from frappe import _

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.members.services.socio_transitions import cambiar_estado

_ROLES_OPERACION = frozenset({"Secretaria", "System Manager"})

_TRANSICIONES: dict[str, tuple[frozenset[str], str]] = {
	"omitir_pago": (frozenset({"Pendiente de Pago"}), ESTADO_SOCIO_PENDIENTE_INSCRIPCION),
	"activar": (
		frozenset(
			{
				"Pendiente de Pago",
				ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
				"Pendiente de Validación",
				"Suspendido",
			}
		),
		"Activo",
	),
	"marcar_moroso": (frozenset({"Activo"}), "Moroso"),
	"reactivar": (frozenset({"Moroso"}), "Activo"),
	"suspender": (frozenset({"Activo"}), "Suspendido"),
	"dar_baja": (
		frozenset(
			{
				"Activo",
				"Moroso",
				"Suspendido",
				"Pendiente de Pago",
				ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
			}
		),
		"Baja",
	),
}


def ensure_secretaria_operacion_access() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if not _ROLES_OPERACION.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def _aplicar_transicion(
	socio_name: str,
	operacion: str,
	*,
	motivo: str | None = None,
) -> str:
	ensure_secretaria_operacion_access()
	if not frappe.db.exists("Socio", socio_name):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)

	estados_origen, estado_destino = _TRANSICIONES[operacion]
	estado_actual = frappe.db.get_value("Socio", socio_name, "estado")
	if estado_actual not in estados_origen:
		frappe.throw(
			_("No se puede ejecutar «{0}» desde el estado «{1}».").format(
				operacion.replace("_", " "), estado_actual
			),
			frappe.ValidationError,
		)

	motivo_final = (motivo or "").strip() or operacion.replace("_", " ").title()
	cambiar_estado(socio_name, estado_destino, motivo=motivo_final)
	return estado_destino


def omitir_pago_manual(socio_name: str, *, motivo: str | None = None) -> str:
	"""`Pendiente de Pago` → `Pendiente de Inscripción` (bypass pago online)."""
	return _aplicar_transicion(socio_name, "omitir_pago", motivo=motivo or "Alta manual sin pago online")


def activar_socio_manual(socio_name: str, *, motivo: str | None = None) -> str:
	"""Activa al socio sin exigir inscripciones."""
	return _aplicar_transicion(socio_name, "activar", motivo=motivo or "Activación manual Secretaría")


def marcar_moroso(socio_name: str, *, motivo: str | None = None) -> str:
	return _aplicar_transicion(socio_name, "marcar_moroso", motivo=motivo or "Marcado moroso por Secretaría")


def reactivar_socio(socio_name: str, *, motivo: str | None = None) -> str:
	return _aplicar_transicion(socio_name, "reactivar", motivo=motivo or "Reactivación manual Secretaría")


def suspender_socio(socio_name: str, *, motivo: str | None = None) -> str:
	return _aplicar_transicion(socio_name, "suspender", motivo=motivo or "Suspensión manual Secretaría")


def dar_baja_socio(socio_name: str, *, motivo: str | None = None) -> str:
	if not (motivo or "").strip():
		frappe.throw(_("Indique el motivo de baja."), frappe.ValidationError)
	return _aplicar_transicion(socio_name, "dar_baja", motivo=motivo)
