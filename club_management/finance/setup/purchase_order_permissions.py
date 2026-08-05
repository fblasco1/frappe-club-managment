"""Permisos operativos de Purchase Order para Tesorería y Secretaría (GF-6).

"Crear Orden de Compra" es una operación central del panel de Tesorería. Ni
`Tesoreria` ni `Secretaria` tenían acceso a `Purchase Order`, por eso lo
habilitamos aquí.

IMPORTANTE (Frappe): al agregar un `Custom DocPerm`, los `DocPerm` estándar del
DocType quedan ignorados. Para no perder acceso administrativo, agregamos
explícitamente permisos completos para `System Manager` además de los roles del
club. Los roles estándar de compras de ERPNext no se usan en este sitio.
"""

from __future__ import annotations

import frappe

from club_management.finance.permissions import (
	ROLE_SECRETARIA,
	ROLE_SYSTEM_MANAGER,
	ROLE_TESORERIA,
	ensure_role_tesoreria_exists,
)

DOCTYPE = "Purchase Order"

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

_OPERATIVE = {
	"read": 1,
	"write": 1,
	"create": 1,
	"submit": 1,
	"report": 1,
	"export": 1,
	"print": 1,
}

_FULL = {flag: 1 for flag in _PERM_FLAGS}

# role -> perms
PERMISOS: dict[str, dict[str, int]] = {
	ROLE_SYSTEM_MANAGER: _FULL,
	ROLE_TESORERIA: _OPERATIVE,
	ROLE_SECRETARIA: _OPERATIVE,
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


def ensure_purchase_order_permissions() -> None:
	"""Asegura permisos operativos de Purchase Order para los roles del club.

	Histórico: el club dejó de usar `Purchase Order`. Ver
	`remove_purchase_order_club_permissions`.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	ensure_role_tesoreria_exists()
	for role, perms in PERMISOS.items():
		_ensure_perm(role, perms)
	frappe.clear_cache()


def remove_purchase_order_club_permissions() -> None:
	"""Elimina los Custom DocPerm de Purchase Order de los roles del club.

	Al borrar todos los Custom DocPerm de `Purchase Order`, el DocType vuelve a sus
	`DocPerm` estándar de ERPNext (System Manager, Purchase Manager, etc.) y los roles
	del club (`Tesoreria`, `Secretaria`) pierden acceso. El flujo de egresos pasa a
	usar exclusivamente `Purchase Invoice`.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	for role in (ROLE_SYSTEM_MANAGER, ROLE_TESORERIA, ROLE_SECRETARIA):
		for name in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": DOCTYPE, "role": role},
			pluck="name",
		):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=1)
	frappe.clear_cache()
