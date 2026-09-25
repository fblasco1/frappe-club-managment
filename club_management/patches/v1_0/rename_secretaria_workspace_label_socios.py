"""Sincroniza label/title del workspace (legacy label-only rename).

Superseded by `rename_secretaria_workspace_to_socios` (name=title=Socios).
Se mantiene no-op seguro si el workspace ya se renombró.
"""

from __future__ import annotations

import frappe

from club_management.members.setup.secretaria_workspace import WORKSPACE_LABEL, WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace_sidebar import (
	sync_secretaria_workspace_sidebar,
)


def execute() -> None:
	# Compat: sitios que aún tengan name Secretaría antes del patch de rename.
	legacy = "Secretaría"
	target = WORKSPACE_NAME if frappe.db.exists("Workspace", WORKSPACE_NAME) else legacy
	if not frappe.db.exists("Workspace", target):
		return

	frappe.db.set_value(
		"Workspace",
		target,
		{"label": WORKSPACE_LABEL, "title": WORKSPACE_LABEL},
		update_modified=False,
	)
	if target == WORKSPACE_NAME:
		sync_secretaria_workspace_sidebar()

	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Workspace Sidebar")
