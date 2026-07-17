"""Carga rápida de ingresos (Sales Invoice) y egresos (Purchase Invoice)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.finance.permissions import ensure_carga_rapida_access
from club_management.members.services.modos_pago_desk import validar_modo_pago_desk
from club_management.setup.icdpe_company import resolve_icdpe_company

SALES_INVOICE_DOCTYPE = "Sales Invoice"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"

CLUB_CONCEPTOS = frozenset({"Personal", "Deportiva", "Infraestructura", "Estructura"})

# Customer genérico para ingresos no-socio (buffet, entradas, etc.)
FINANCE_WALK_IN_CUSTOMER = "ICDPE-Cliente Contado"


def erpnext_finance_disponible() -> bool:
	return bool(
		frappe.db.exists("DocType", SALES_INVOICE_DOCTYPE)
		and frappe.db.exists("DocType", PURCHASE_INVOICE_DOCTYPE)
	)


def _resolve_item_default_row(item_code: str, company: str) -> Any | None:
	item = frappe.get_doc("Item", item_code)
	for row in item.get("item_defaults") or []:
		if row.company == company:
			return row
	return None


def resolve_selling_cost_center(item_code: str, company: str, explicit: str | None = None) -> str:
	if explicit:
		if not frappe.db.exists("Cost Center", explicit):
			frappe.throw(_("Cost Center {0} no existe.").format(explicit), frappe.ValidationError)
		return explicit
	row = _resolve_item_default_row(item_code, company)
	cc = (row.selling_cost_center if row else None) or None
	if not cc:
		frappe.throw(
			_("Falta Cost Center para el ítem {0} (selling_cost_center).").format(item_code),
			frappe.ValidationError,
		)
	return cc


def resolve_buying_cost_center(item_code: str, company: str, explicit: str | None = None) -> str:
	if explicit:
		if not frappe.db.exists("Cost Center", explicit):
			frappe.throw(_("Cost Center {0} no existe.").format(explicit), frappe.ValidationError)
		return explicit
	row = _resolve_item_default_row(item_code, company)
	cc = (row.buying_cost_center if row else None) or (row.selling_cost_center if row else None)
	if not cc:
		frappe.throw(
			_("Falta Cost Center para el ítem {0} (buying_cost_center).").format(item_code),
			frappe.ValidationError,
		)
	return cc


def _validate_club_concepto(club_concepto: str | None) -> str | None:
	if not club_concepto:
		return None
	concepto = club_concepto.strip()
	if concepto not in CLUB_CONCEPTOS:
		frappe.throw(
			_("Categoría inválida: {0}. Use Personal, Deportiva, Infraestructura o Estructura.").format(
				concepto
			),
			frappe.ValidationError,
		)
	return concepto


def ensure_walk_in_customer(company: str) -> str:
	"""Customer genérico para ingresos de mostrador / eventuales."""
	existing = frappe.db.get_value("Customer", {"customer_name": "Cliente Contado ICDPE"}, "name")
	if existing:
		return existing
	if frappe.db.exists("Customer", FINANCE_WALK_IN_CUSTOMER):
		return FINANCE_WALK_IN_CUSTOMER

	customer_group = (
		frappe.db.get_single_value("Selling Settings", "customer_group")
		or frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		or "All Customer Groups"
	)
	territory = (
		frappe.db.get_single_value("Selling Settings", "territory")
		or frappe.db.get_value("Territory", {"is_group": 0}, "name")
		or "All Territories"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": "Cliente Contado ICDPE",
			"customer_type": "Individual",
			"customer_group": customer_group,
			"territory": territory,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _set_club_concepto(doc: Any, club_concepto: str | None) -> None:
	concepto = _validate_club_concepto(club_concepto)
	if concepto and frappe.get_meta(doc.doctype).has_field("club_concepto"):
		doc.club_concepto = concepto


def _submit_payment_against(
	voucher_type: str,
	voucher_name: str,
	*,
	mode_of_payment: str | None,
	posting_date: str | date | None = None,
) -> str:
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	except ImportError as exc:
		raise frappe.ValidationError(_("ERPNext no está disponible.")) from exc

	fecha = getdate(posting_date or today())
	if fecha > getdate(today()):
		frappe.throw(_("La fecha de pago/cobro no puede ser posterior a hoy."), frappe.ValidationError)

	pe = get_payment_entry(voucher_type, voucher_name)
	pe.mode_of_payment = validar_modo_pago_desk(mode_of_payment)
	pe.posting_date = fecha
	if not pe.reference_no:
		pe.reference_no = voucher_name
	pe.reference_date = fecha
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def registrar_ingreso(
	*,
	item_code: str,
	amount: float,
	cost_center: str | None = None,
	customer: str | None = None,
	posting_date: str | date | None = None,
	due_date: str | date | None = None,
	cobrado_ahora: bool = False,
	mode_of_payment: str | None = None,
	club_concepto: str | None = None,
	remarks: str | None = None,
	skip_permission_check: bool = False,
) -> dict[str, str | None]:
	"""Crea Sales Invoice (y opcionalmente Payment Entry Receive)."""
	if not skip_permission_check:
		ensure_carga_rapida_access()
	if not erpnext_finance_disponible():
		frappe.throw(_("ERPNext no está disponible para finanzas."), frappe.ValidationError)
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Ítem {0} no existe.").format(item_code), frappe.DoesNotExistError)

	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	monto = flt(amount)
	if monto <= 0:
		frappe.throw(_("El monto debe ser mayor a cero."), frappe.ValidationError)

	company = resolve_icdpe_company()
	cc = resolve_selling_cost_center(item_code, company, cost_center)
	party = customer or ensure_walk_in_customer(company)
	fecha = getdate(posting_date or today())
	vence = getdate(due_date or fecha)

	invoice = frappe.get_doc(
		{
			"doctype": SALES_INVOICE_DOCTYPE,
			"company": company,
			"customer": party,
			"posting_date": fecha,
			"due_date": vence,
			"set_posting_time": 1,
			"update_stock": 0,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": monto,
					"cost_center": cc,
				}
			],
			"remarks": remarks or f"Ingreso carga rápida {item_code}",
		}
	)
	_set_club_concepto(invoice, club_concepto)
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	pe_name: str | None = None
	if cobrado_ahora:
		pe_name = _submit_payment_against(
			SALES_INVOICE_DOCTYPE,
			invoice.name,
			mode_of_payment=mode_of_payment,
			posting_date=fecha,
		)

	return {"sales_invoice": invoice.name, "payment_entry": pe_name}


def _ensure_company_ready_for_service_purchases(company: str) -> None:
	"""Desactiva inventario perpetuo si falta cuenta stock (PI de servicios)."""
	if not frappe.db.get_value("Company", company, "enable_perpetual_inventory"):
		return
	stock_rbnb = frappe.db.get_value("Company", company, "stock_received_but_not_billed")
	if stock_rbnb and frappe.db.exists("Account", stock_rbnb):
		return
	frappe.db.set_value(
		"Company",
		company,
		"enable_perpetual_inventory",
		0,
		update_modified=False,
	)


def registrar_egreso(
	*,
	supplier: str,
	item_code: str,
	amount: float,
	due_date: str | date,
	cost_center: str | None = None,
	posting_date: str | date | None = None,
	pagado_ahora: bool = False,
	mode_of_payment: str | None = None,
	club_concepto: str | None = None,
	remarks: str | None = None,
	skip_permission_check: bool = False,
) -> dict[str, str | None]:
	"""Crea Purchase Invoice (y opcionalmente Payment Entry Pay)."""
	if not skip_permission_check:
		ensure_carga_rapida_access()
	if not erpnext_finance_disponible():
		frappe.throw(_("ERPNext no está disponible para finanzas."), frappe.ValidationError)
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Proveedor {0} no existe.").format(supplier), frappe.DoesNotExistError)
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Ítem {0} no existe.").format(item_code), frappe.DoesNotExistError)

	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	monto = flt(amount)
	if monto <= 0:
		frappe.throw(_("El monto debe ser mayor a cero."), frappe.ValidationError)

	concepto = _validate_club_concepto(club_concepto)
	if not concepto:
		frappe.throw(
			_("Debe indicar club_concepto (Personal, Deportiva, Infraestructura o Estructura)."),
			frappe.ValidationError,
		)

	company = resolve_icdpe_company()
	_ensure_company_ready_for_service_purchases(company)
	cc = resolve_buying_cost_center(item_code, company, cost_center)
	fecha = getdate(posting_date or today())
	vence = getdate(due_date)

	# expense_account desde Item Default si existe
	expense_account = None
	row = _resolve_item_default_row(item_code, company)
	if row and row.get("expense_account"):
		expense_account = row.expense_account

	item_row: dict[str, Any] = {
		"item_code": item_code,
		"qty": 1,
		"rate": monto,
		"cost_center": cc,
	}
	if expense_account:
		item_row["expense_account"] = expense_account

	invoice = frappe.get_doc(
		{
			"doctype": PURCHASE_INVOICE_DOCTYPE,
			"company": company,
			"supplier": supplier,
			"posting_date": fecha,
			"due_date": vence,
			"set_posting_time": 1,
			"update_stock": 0,
			"bill_no": f"CR-{frappe.generate_hash(length=8)}",
			"bill_date": fecha,
			"items": [item_row],
			"remarks": remarks or f"Egreso carga rápida {item_code}",
		}
	)
	_set_club_concepto(invoice, concepto)
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	pe_name: str | None = None
	if pagado_ahora:
		pe_name = _submit_payment_against(
			PURCHASE_INVOICE_DOCTYPE,
			invoice.name,
			mode_of_payment=mode_of_payment,
			posting_date=fecha,
		)

	return {"purchase_invoice": invoice.name, "payment_entry": pe_name}
