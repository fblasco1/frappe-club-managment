"""Notificaciones del flujo Solicitud de Asociación."""

from __future__ import annotations

import frappe
from frappe import _
from club_management.members.email_templates.solicitud_emails import (
	render_solicitud_requiere_correccion_email,
	render_solicitud_validada_contacto_email,
	render_solicitud_validada_email,
)
from club_management.members.services.solicitud_tokens import (
	build_pago_stub_url,
	sign_pago_token,
)


def _pago_online_alta_habilitado() -> bool:
	"""True solo si Club Settings pide link de pago al validar (Cobros Plus)."""
	try:
		return bool(frappe.db.get_single_value("Club Settings", "habilitar_pago_online_alta"))
	except Exception:
		return False


def enqueue_validacion_pago_email(solicitud_name: str, to_email: str) -> None:
	if not to_email:
		return
	frappe.enqueue(
		"club_management.members.services.solicitud_notificaciones._send_validacion_pago_email",
		queue="short",
		solicitud_name=solicitud_name,
		to_email=to_email,
		enqueue_after_commit=True,
	)


def enqueue_correccion_email(solicitud_name: str) -> None:
	frappe.enqueue(
		"club_management.members.services.solicitud_notificaciones._send_correccion_email",
		queue="short",
		solicitud_name=solicitud_name,
		enqueue_after_commit=True,
	)


def _send_validacion_pago_email(solicitud_name: str, to_email: str) -> None:
	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if _pago_online_alta_habilitado():
		pago_token = sign_pago_token(solicitud_name)
		pago_url = build_pago_stub_url(pago_token)
		html = render_solicitud_validada_email(
			nombre=solicitud.nombre,
			pago_url=pago_url,
		)
		subject = _("Solicitud validada — primera cuota")
	else:
		html = render_solicitud_validada_contacto_email(nombre=solicitud.nombre)
		subject = _("Solicitud validada — próximo paso")
	frappe.sendmail(
		recipients=[to_email],
		subject=subject,
		message=html,
		delayed=False,
	)


def _send_correccion_email(solicitud_name: str) -> None:
	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if not solicitud.email:
		return
	html = render_solicitud_requiere_correccion_email(
		nombre=solicitud.nombre,
		token_seguimiento=solicitud.token_seguimiento or "",
		observaciones=solicitud.observaciones_secretaria or "",
	)
	frappe.sendmail(
		recipients=[solicitud.email],
		subject=_("Solicitud de asociación — corrección requerida"),
		message=html,
		delayed=False,
	)
