"""Notificaciones del flujo Solicitud de Asociación (stubs Sprint 1).

Commit 5 implementará plantillas y enlaces de pago; Commit 4 solo expone
`enqueue_validacion_pago_email` para encolar (o registrar en tests).
"""

from __future__ import annotations

import frappe


def enqueue_validacion_pago_email(solicitud_name: str, to_email: str) -> None:
	"""Encola (o registra) el email de primera cuota tras validar una solicitud."""
	if not to_email:
		return

	# Commit 5: frappe.sendmail con plantilla `solicitud_validada`.
	frappe.enqueue(
		"club_management.members.services.solicitud_notificaciones._send_validacion_pago_stub",
		queue="short",
		solicitud_name=solicitud_name,
		to_email=to_email,
		enqueue_after_commit=True,
	)


def _send_validacion_pago_stub(solicitud_name: str, to_email: str) -> None:
	frappe.logger("solicitud_notificaciones").info(
		"validacion_pago_email_stub solicitud=%s to=%s", solicitud_name, to_email
	)
