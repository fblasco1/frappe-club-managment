"""Completa defaults contables de la Company ICDPE para facturar y cobrar."""

from __future__ import annotations

import frappe
from frappe import _

COMPANY = "Institución Cultural y Deportiva Pedro Echagüe"
COMPANY_ABBR = "ICDPE"

ACCOUNTS = {
	"caja_ars": "111101 - Caja ARS - ICDPE",
	"banco_ars": "111201 - Banco ARS - ICDPE",
	"cuotas_sociales_cobrar": "114001 - Cuotas sociales a cobrar - ICDPE",
	"deudores_ventas": "114002 - Deudores por ventas - ICDPE",
	"cuota_social_ingreso": "411001 - Cuota social - ICDPE",
	"otros_ingresos_parent": "4900 - Otros ingresos - ICDPE",
	"write_off": "491001 - Otros ingresos (uso restringido) - ICDPE",
}

ROUND_OFF_NUMBER = "491002"
ROUND_OFF_LABEL = "Diferencias de redondeo"

MISSING_COST_CENTERS: tuple[tuple[str, str], ...] = (
	("Actividades - Zumba", "Actividades - ICDPE"),
)


def _account_exists(name: str) -> bool:
	return bool(name and frappe.db.exists("Account", name))


def ensure_round_off_account() -> str:
	"""Crea cuenta Round Off si el plan ICDPE no la trae."""
	existing = frappe.db.get_value(
		"Account",
		{"company": COMPANY, "account_number": ROUND_OFF_NUMBER},
		"name",
	)
	if existing:
		return existing

	if not _account_exists(ACCOUNTS["otros_ingresos_parent"]):
		frappe.throw(_("Falta la cuenta padre «Otros ingresos» en {0}.").format(COMPANY))

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": ROUND_OFF_LABEL,
			"parent_account": ACCOUNTS["otros_ingresos_parent"],
			"company": COMPANY,
			"account_number": ROUND_OFF_NUMBER,
			"account_type": "Round Off",
			"is_group": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_missing_cost_centers() -> list[str]:
	created: list[str] = []
	for cost_center_name, parent in MISSING_COST_CENTERS:
		full_name = f"{cost_center_name} - {COMPANY_ABBR}"
		if frappe.db.exists("Cost Center", full_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": cost_center_name,
				"parent_cost_center": parent,
				"company": COMPANY,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		created.append(full_name)
	return created


def _ensure_mode_of_payment_account(mode: str, account: str) -> None:
	if not frappe.db.exists("Mode of Payment", mode):
		return
	mop = frappe.get_doc("Mode of Payment", mode)
	for row in mop.accounts or []:
		if row.company == COMPANY:
			if row.default_account != account:
				row.default_account = account
				mop.save(ignore_permissions=True)
			return
	mop.append("accounts", {"company": COMPANY, "default_account": account})
	mop.save(ignore_permissions=True)


def ensure_mode_of_payment_accounts() -> None:
	_ensure_mode_of_payment_account("Cash", ACCOUNTS["caja_ars"])
	for mode in ("Cheque", "Wire Transfer", "Bank Draft", "Credit Card"):
		_ensure_mode_of_payment_account(mode, ACCOUNTS["banco_ars"])


def complete_company_defaults() -> dict[str, str | None]:
	"""Setea cuentas por defecto en la Company ICDPE."""
	round_off = ensure_round_off_account()
	company = frappe.get_doc("Company", COMPANY)
	updates: dict[str, str | None] = {
		"round_off_account": round_off,
		"default_receivable_account": ACCOUNTS["cuotas_sociales_cobrar"],
		"default_income_account": ACCOUNTS["cuota_social_ingreso"],
		"default_cash_account": ACCOUNTS["caja_ars"],
		"default_bank_account": ACCOUNTS["banco_ars"],
		"write_off_account": ACCOUNTS["write_off"],
		"cost_center": "Administración - ICDPE",
	}
	for field, value in updates.items():
		if value and company.get(field) != value:
			company.set(field, value)
	company.save(ignore_permissions=True)
	return {k: company.get(k) for k in updates}


def sync_club_settings_item_cuota() -> None:
	"""Enlaza Club Settings al ítem institucional ICDPE-CUOTA-SOCIAL."""
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	item = "ICDPE-CUOTA-SOCIAL"
	if not frappe.db.exists("Item", item):
		return
	settings = frappe.get_single("Club Settings")
	settings.company = COMPANY
	settings.item_cuota_social = item
	for row in settings.cuotas_categoria or []:
		if not row.item:
			row.item = item
	settings.save(ignore_permissions=True)


def setup_icdpe_company_accounting(*, create_items: bool = True) -> dict:
	"""Orquesta setup contable ICDPE (idempotente)."""
	if not frappe.db.exists("Company", COMPANY):
		frappe.throw(_("No existe la Company {0}.").format(COMPANY))

	cost_centers = ensure_missing_cost_centers()
	company_defaults = complete_company_defaults()
	ensure_mode_of_payment_accounts()

	items_result: dict | None = None
	if create_items:
		from club_management.setup.icdpe_create_service_items import run as run_items

		items_result = run_items()

	sync_club_settings_item_cuota()

	return {
		"company": COMPANY,
		"cost_centers_created": cost_centers,
		"company_defaults": company_defaults,
		"items": items_result,
	}
