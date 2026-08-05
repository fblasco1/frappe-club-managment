"""Permisos operativos de Finanzas para el rol Secretaría (GF-6).

Secretaría carga la provisión de sueldos y otros egresos operativos, por eso
necesita **crear/leer Facturas de compra, Pagos y proveedores**. NO recibe
acceso al flujo de fondos ni a reportes P&L (siguen protegidos por rol vía
`ensure_tesoreria_access` y los `roles` del reporte).

IMPORTANTE (comportamiento Frappe): si un DocType tiene algún `Custom DocPerm`,
los `DocPerm` estándar quedan ignorados (ver `frappe.permissions.get_valid_perms`).
Por eso solo agregamos permisos a DocTypes que **ya** están en «modo custom»
(los del patch `add_tesoreria_accounting_permissions`). Agregar Custom DocPerm a
un DocType que no lo tenga borraría sus permisos estándar para el resto de roles.
"""

from __future__ import annotations

import frappe

from club_management.finance.permissions import ROLE_SECRETARIA

# DocTypes que ya están en «modo custom» por el patch de Tesorería.
# Solo sobre estos es seguro agregar Custom DocPerm.
DOCTYPES_EN_MODO_CUSTOM: frozenset[str] = frozenset(
	{
		"Account",
		"Cost Center",
		"GL Entry",
		"Sales Invoice",
		"Purchase Invoice",
		"Payment Entry",
		"Journal Entry",
		"Customer",
		"Supplier",
		"Item",
		"Mode of Payment",
		"Company",
	}
)

# Permisos operativos a asegurar para Secretaría (permlevel 0).
# NOTA: `Purchase Invoice` se gestiona en `purchase_invoice_permissions.py`
# (draft-only: sin submit para Secretaría). No declararlo aquí.
OPERATIVE_PERMS: dict[str, dict[str, int]] = {
	"Payment Entry": {
		"read": 1,
		"write": 1,
		"create": 1,
		"submit": 1,
		"print": 1,
		"report": 1,
	},
	"Supplier": {"read": 1, "write": 1, "create": 1, "select": 1},
	# Item: Secretaría alta/edita catálogo operativo y lo selecciona en Links.
	"Item": {
		"read": 1,
		"select": 1,
		"write": 1,
		"create": 1,
		"report": 1,
		"print": 1,
	},
	# Masters de solo lectura (con select para Link fields).
	"Account": {"read": 1, "select": 1},
	"Cost Center": {"read": 1, "select": 1},
	"Company": {"read": 1, "select": 1},
	"Mode of Payment": {"read": 1, "select": 1},
}

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
	"select",
)


def _ensure_perm(doctype: str, role: str, perms: dict[str, int]) -> bool:
	if doctype not in DOCTYPES_EN_MODO_CUSTOM:
		# No tocar DocTypes con permisos estándar: agregar Custom DocPerm los borraría.
		return False
	if not frappe.db.exists("DocType", doctype):
		return False

	existing = frappe.db.exists(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}
	)
	if existing:
		doc = frappe.get_doc("Custom DocPerm", existing)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
			}
		)

	changed = not existing
	for flag in _PERM_FLAGS:
		if not frappe.get_meta("Custom DocPerm").has_field(flag):
			continue
		valor = int(perms.get(flag, 0))
		if int(doc.get(flag) or 0) != valor:
			doc.set(flag, valor)
			changed = True

	if not changed:
		return True
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	return True


def ensure_secretaria_finance_permissions() -> None:
	"""Asegura permisos operativos de Finanzas para el rol Secretaría."""
	for doctype, perms in OPERATIVE_PERMS.items():
		_ensure_perm(doctype, ROLE_SECRETARIA, perms)
	frappe.clear_cache()
