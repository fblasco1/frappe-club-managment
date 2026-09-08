"""Contexto de la página pública `/solicitud-seguimiento`."""

from __future__ import annotations

import frappe


def get_context(context) -> None:
	# Página pública, no cachear (depende del token).
	context.no_cache = 1
	context.token = (frappe.form_dict.get("token") or "").strip()
