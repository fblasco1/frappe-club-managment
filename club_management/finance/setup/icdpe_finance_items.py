"""Catálogo de Items financieros ICDPE (ingresos eventuales + egresos)."""

from __future__ import annotations

from dataclasses import dataclass

import frappe

from club_management.setup.icdpe_company import resolve_icdpe_company

DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"
ADMIN_CC = "Administración - ICDPE"
BUFFET_CC = "Gastronomía - Buffet - ICDPE"
RESTAURANTE_CC = "Gastronomía - Restaurante - ICDPE"
ALQUILER_TEMP_CC = "Alquileres - Temporal - ICDPE"
BASQUET_CC = "Deportes - Basquet - ICDPE"


@dataclass(frozen=True)
class FinanceItemSpec:
	item_code: str
	item_name: str
	item_group: str
	account_number: str  # income o expense según is_purchase
	cost_center_name: str
	is_sales: bool = True
	is_purchase: bool = False


INCOME_SPECS: tuple[FinanceItemSpec, ...] = (
	FinanceItemSpec(
		"ICDPE-FIN-ENTRADAS",
		"Entradas partidos / eventos",
		"ICDPE / Finanzas ingresos",
		"431003",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INDUMENTARIA",
		"Venta indumentaria",
		"ICDPE / Finanzas ingresos",
		"451002",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-BUFFET",
		"Ventas buffet",
		"ICDPE / Finanzas ingresos",
		"441001",
		BUFFET_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-RESTAURANTE",
		"Ventas restaurante",
		"ICDPE / Finanzas ingresos",
		"441001",
		RESTAURANTE_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-CANON-CONCESION",
		"Canon concesión buffet/restaurante",
		"ICDPE / Finanzas ingresos",
		"441001",
		BUFFET_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SPONSOR",
		"Sponsoreo y publicidad",
		"ICDPE / Finanzas ingresos",
		"451001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ALQUILER-TEMP",
		"Alquiler temporal instalaciones",
		"ICDPE / Finanzas ingresos",
		"421001",
		ALQUILER_TEMP_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SUBSIDIO",
		"Subsidios gubernamentales",
		"ICDPE / Finanzas ingresos",
		"491001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-DONACION",
		"Donaciones",
		"ICDPE / Finanzas ingresos",
		"491001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-EVENTO-RECAUDACION",
		"Eventos de recaudación (rifas, cenas)",
		"ICDPE / Finanzas ingresos",
		"431003",
		ADMIN_CC,
	),
)

EXPENSE_SPECS: tuple[FinanceItemSpec, ...] = (
	FinanceItemSpec(
		"ICDPE-FIN-SUELDOS",
		"Sueldos personal",
		"ICDPE / Finanzas egresos",
		"511001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-CARGAS-931",
		"Cargas sociales / Formulario 931",
		"ICDPE / Finanzas egresos",
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-UTEDYC",
		"Aportes sindicales UTEDYC",
		"ICDPE / Finanzas egresos",
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ART",
		"ART",
		"ICDPE / Finanzas egresos",
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ENTRENADORES",
		"Honorarios entrenadores / profesores",
		"ICDPE / Finanzas egresos",
		"513001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INSUMOS-DEP",
		"Insumos deportivos",
		"ICDPE / Finanzas egresos",
		"541001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-FEDERACION",
		"Pagos a federaciones",
		"ICDPE / Finanzas egresos",
		"543001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-VIATICOS",
		"Viáticos y traslados",
		"ICDPE / Finanzas egresos",
		"544001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ARBITROS",
		"Árbitros / oficiales de mesa",
		"ICDPE / Finanzas egresos",
		"542001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SEGURIDAD",
		"Seguridad privada / policía partidos",
		"ICDPE / Finanzas egresos",
		"533001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-MANT-IMPLEMENTOS",
		"Mantenimiento implementos deportivos",
		"ICDPE / Finanzas egresos",
		"531001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-MANT-INSTALACIONES",
		"Mantenimiento instalaciones",
		"ICDPE / Finanzas egresos",
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-OBRAS",
		"Obras de infraestructura",
		"ICDPE / Finanzas egresos",
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-EMERGENCIAS-MED",
		"Abono emergencias médicas",
		"ICDPE / Finanzas egresos",
		"561001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SEGURO-RC",
		"Seguro responsabilidad civil",
		"ICDPE / Finanzas egresos",
		"561001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-LUZ",
		"Electricidad",
		"ICDPE / Finanzas egresos",
		"521001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-GAS",
		"Gas",
		"ICDPE / Finanzas egresos",
		"523001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-AGUA",
		"Agua",
		"ICDPE / Finanzas egresos",
		"522001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-IMPUESTOS",
		"Impuestos",
		"ICDPE / Finanzas egresos",
		"551001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
)


def _ensure_uom(uom_name: str) -> None:
	if frappe.db.exists("UOM", uom_name):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)


def _ensure_item_group(name: str) -> None:
	if frappe.db.exists("Item Group", name):
		return
	if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
		frappe.throw(f"No existe el Item Group raíz '{DEFAULT_ITEM_GROUP_ROOT}'")
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
			"is_group": 0,
		}
	).insert(ignore_permissions=True)


def _resolve_account(company: str, account_number: str) -> str | None:
	rows = frappe.get_all(
		"Account",
		filters={"company": company, "account_number": account_number, "is_group": 0},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _resolve_cost_center(cost_center_name: str) -> str | None:
	if frappe.db.exists("Cost Center", cost_center_name):
		return cost_center_name
	# fallback Administración
	if frappe.db.exists("Cost Center", ADMIN_CC):
		return ADMIN_CC
	return None


def _upsert_item_defaults(
	item_name: str,
	company: str,
	*,
	income_account: str | None,
	expense_account: str | None,
	selling_cc: str | None,
	buying_cc: str | None,
) -> None:
	item = frappe.get_doc("Item", item_name)
	row = None
	for d in item.get("item_defaults") or []:
		if d.company == company:
			row = d
			break
	payload: dict = {"company": company}
	if income_account:
		payload["income_account"] = income_account
	if expense_account:
		payload["expense_account"] = expense_account
	if selling_cc:
		payload["selling_cost_center"] = selling_cc
	if buying_cc:
		payload["buying_cost_center"] = buying_cc

	if row is None:
		item.append("item_defaults", payload)
	else:
		for key, value in payload.items():
			if key != "company" and value:
				row.set(key, value)
	item.save(ignore_permissions=True)


def upsert_finance_item(spec: FinanceItemSpec) -> str:
	"""Crea o actualiza un Item financiero. Devuelve created|updated|skipped."""
	_ensure_uom("Servicio")
	_ensure_item_group(spec.item_group)
	company = resolve_icdpe_company()
	account = _resolve_account(company, spec.account_number)
	cc = _resolve_cost_center(spec.cost_center_name)
	if not account or not cc:
		return "skipped"

	income = account if spec.is_sales else None
	expense = account if spec.is_purchase else None
	selling_cc = cc if spec.is_sales else None
	buying_cc = cc if spec.is_purchase else None

	if frappe.db.exists("Item", spec.item_code):
		item = frappe.get_doc("Item", spec.item_code)
		item.item_name = spec.item_name
		item.item_group = spec.item_group
		item.is_stock_item = 0
		item.stock_uom = "Servicio"
		item.is_sales_item = 1 if spec.is_sales else 0
		item.is_purchase_item = 1 if spec.is_purchase else 0
		item.save(ignore_permissions=True)
		_upsert_item_defaults(
			spec.item_code,
			company,
			income_account=income,
			expense_account=expense,
			selling_cc=selling_cc,
			buying_cc=buying_cc,
		)
		return "updated"

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": spec.item_code,
			"item_name": spec.item_name,
			"item_group": spec.item_group,
			"is_stock_item": 0,
			"is_sales_item": 1 if spec.is_sales else 0,
			"is_purchase_item": 1 if spec.is_purchase else 0,
			"stock_uom": "Servicio",
			"include_item_in_manufacturing": 0,
		}
	).insert(ignore_permissions=True)
	_upsert_item_defaults(
		spec.item_code,
		company,
		income_account=income,
		expense_account=expense,
		selling_cc=selling_cc,
		buying_cc=buying_cc,
	)
	return "created"


def run_finance_items_seed() -> dict[str, int]:
	"""Seed idempotente de todos los ítems financieros."""
	counts = {"created": 0, "updated": 0, "skipped": 0}
	for spec in (*INCOME_SPECS, *EXPENSE_SPECS):
		result = upsert_finance_item(spec)
		counts[result] = counts.get(result, 0) + 1
	return counts
