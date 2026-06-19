"""Fija landing /desk para Secretaría y limpia caché de boot."""

from __future__ import annotations

import frappe

from club_management.members.setup.inicio_workspace import (
	set_secretaria_default_workspace,
	set_secretaria_role_home_page,
)


def execute() -> None:
	set_secretaria_role_home_page()
	set_secretaria_default_workspace(only_if_empty=False)

	for user in frappe.get_all(
		"User",
		filters={"enabled": 1},
		pluck="name",
	):
		frappe.cache.hdel("bootinfo", user)
		frappe.cache.hdel("desktop_icons", user)
