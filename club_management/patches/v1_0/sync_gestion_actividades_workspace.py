"""Vacía widgets estáticos del workspace Gestión de Actividades (panel custom)."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "Gestión de Actividades"


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	ws = frappe.get_doc("Workspace", WORKSPACE_NAME)
	ws.content = json.dumps([])
	ws.shortcuts = []
	ws.save(ignore_permissions=True)
