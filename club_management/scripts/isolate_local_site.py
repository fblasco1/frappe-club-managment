"""Aísla el sitio local: sin scheduler, sin SMTP real, sin webhooks de pasarela."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint


def run() -> dict[str, Any]:
	"""Desactiva disparos externos en un site restaurado desde producción."""
	webhooks = 0
	if frappe.db.exists("DocType", "Webhook"):
		for name in frappe.get_all("Webhook", filters={"enabled": 1}, pluck="name"):
			frappe.db.set_value("Webhook", name, "enabled", 0, update_modified=False)
			webhooks += 1

	emails = 0
	if frappe.db.exists("DocType", "Email Account"):
		for name in frappe.get_all("Email Account", pluck="name"):
			changed = False
			if cint(frappe.db.get_value("Email Account", name, "enable_outgoing")):
				frappe.db.set_value("Email Account", name, "enable_outgoing", 0, update_modified=False)
				changed = True
			if cint(frappe.db.get_value("Email Account", name, "default_outgoing")):
				frappe.db.set_value("Email Account", name, "default_outgoing", 0, update_modified=False)
				changed = True
			if changed:
				emails += 1

	notifications = 0
	if frappe.db.exists("DocType", "Notification"):
		for name in frappe.get_all("Notification", filters={"enabled": 1, "channel": "Email"}, pluck="name"):
			frappe.db.set_value("Notification", name, "enabled", 0, update_modified=False)
			notifications += 1

	frappe.db.commit()
	result = {
		"webhooks_disabled": webhooks,
		"email_accounts_muted": emails,
		"notifications_email_disabled": notifications,
		"pause_scheduler": bool(frappe.conf.get("pause_scheduler")),
		"mute_emails": bool(frappe.conf.get("mute_emails")),
		"developer_mode": bool(frappe.conf.get("developer_mode")),
	}
	print(result)
	return result
