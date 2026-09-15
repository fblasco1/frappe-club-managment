"""Página pública del stub de pago (Sprint 1 — temporal, reemplazar en Sprint 4)."""

import frappe

from club_management.members.services.solicitud_tokens import (
	normalize_pago_token_from_request,
	verify_pago_token,
)
from club_management.members.workflow.solicitud_asociacion_workflow import STATE_VALIDADA


def get_context(context):
	token = normalize_pago_token_from_request(frappe.form_dict.get("token"))
	context.no_cache = 1
	context.pago_token = token
	context.pago_valido = False
	context.nombre_solicitante = ""

	if not token:
		return

	solicitud_name = verify_pago_token(token)
	if not solicitud_name:
		return

	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if solicitud.workflow_state != STATE_VALIDADA or not solicitud.socio_generado:
		return

	context.pago_valido = True
	context.nombre_solicitante = solicitud.nombre or ""
