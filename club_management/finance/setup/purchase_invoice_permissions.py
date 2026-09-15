"""Permisos de Purchase Invoice para el flujo Borrador → Aprobación.

Flujo único de egresos (ver `flujo_egresos_borrador_aprobacion.md`):
- **Secretaría**: crea/edita en Borrador. `read/write/create` pero **sin** `submit`/`cancel`.
- **Tesorería**: permisos **totales** (aprueba con `submit`, rechaza con `cancel`/`delete`).
- **System Manager**: full (el DocType está en «modo custom», así que debe declararse
  explícitamente para no perder acceso administrativo).

IMPORTANTE (Frappe): al existir `Custom DocPerm`, los `DocPerm` estándar se ignoran; por
eso definimos aquí todos los roles relevantes de forma explícita.
"""

from __future__ import annotations

import frappe

from club_management.finance.permissions import (
	ROLE_SECRETARIA,
	ROLE_SYSTEM_MANAGER,
	ROLE_TESORERIA,
	ensure_role_tesoreria_exists,
)

DOCTYPE = "Purchase Invoice"

_PERM_FLAGS = (
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"print",
	"email",
	"share",
)

_FULL = {flag: 1 for flag in _PERM_FLAGS}

# Secretaría: solo Borrador (sin submit/cancel/delete/amend).
_SECRETARIA_DRAFT = {
	"read": 1,
	"write": 1,
	"create": 1,
	"print": 1,
	"report": 1,
	"export": 1,
}

PERMISOS: dict[str, dict[str, int]] = {
	ROLE_SYSTEM_MANAGER: _FULL,
	ROLE_TESORERIA: _FULL,
	ROLE_SECRETARIA: _SECRETARIA_DRAFT,
}


def _ensure_perm(role: str, perms: dict[str, int]) -> None:
	existing = frappe.db.exists(
		"Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0}
	)
	if existing:
		doc = frappe.get_doc("Custom DocPerm", existing)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": DOCTYPE,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
			}
		)

	changed = not existing
	for flag in _PERM_FLAGS:
		valor = int(perms.get(flag, 0))
		if int(doc.get(flag) or 0) != valor:
			doc.set(flag, valor)
			changed = True

	if not changed:
		return
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)


def ensure_purchase_invoice_permissions() -> None:
	"""Asegura permisos de Purchase Invoice (Secretaría draft-only, Tesorería full)."""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	ensure_role_tesoreria_exists()
	for role, perms in PERMISOS.items():
		_ensure_perm(role, perms)
	frappe.clear_cache()
