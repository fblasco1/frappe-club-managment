"""Página pública de elección de actividades tras el pago stub."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.members.services.solicitud_tokens import (
	normalize_pago_token_from_request,
	verify_pago_token,
)
from club_management.members.workflow.solicitud_asociacion_workflow import STATE_VALIDADA


def get_context(context):
	token = normalize_pago_token_from_request(frappe.form_dict.get("token"))
	context.no_cache = 1
	context.pago_token = token
	context.inscripcion_valida = False
	context.nombre_solicitante = ""
	context.ya_activo = False

	if not token:
		return

	solicitud_name = verify_pago_token(token)
	if not solicitud_name:
		return

	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if solicitud.workflow_state != STATE_VALIDADA or not solicitud.socio_generado:
		return

	socio = frappe.get_doc("Socio", solicitud.socio_generado)
	if socio.estado not in (ESTADO_SOCIO_PENDIENTE_INSCRIPCION, "Activo"):
		return

	context.inscripcion_valida = True
	context.nombre_solicitante = " ".join(
		part
		for part in ((socio.nombre or "").strip(), (socio.apellido or "").strip())
		if part
	) or (solicitud.nombre or "")
	context.ya_activo = socio.estado == "Activo"
