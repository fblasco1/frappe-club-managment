"""Compatibilidad ERPNext + PostgreSQL (sin modificar erpnext).

- Payment Ledger: GROUP BY estricto en consultas de saldo.
- Period Closing Voucher: MAX sin ORDER BY inválido en get_value.
- Cancelación de facturas: `delinked`/`is_cancelled` como smallint, no boolean.
- Payment Entry: literales de voucher_type y COALESCE en get_negative_outstanding_invoices.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, now, flt
from frappe import qb
from frappe.query_builder import AliasedQuery, Case, Criterion, Table
from frappe.query_builder.functions import Count, Max, Min, Sum
from frappe.query_builder import Tuple


def apply_patch() -> None:
	"""Idempotente; solo aplica en sitios PostgreSQL con ERPNext."""
	if frappe.db.db_type != "postgres":
		return

	_patch_payment_ledger_query()
	_patch_validate_against_pcv()
	_patch_delink_original_entry()
	_patch_payment_entry_sql()
	_patch_held_invoices()


def _pg_amount_expr(rounded_field: str, grand_field: str) -> str:
	"""Equivalente PG de `if(rounded, rounded, grand)` en SQL MariaDB de ERPNext."""
	return f"COALESCE(NULLIF({rounded_field}, 0), {grand_field})"


def _patch_payment_entry_sql() -> None:
	try:
		import erpnext.accounts.doctype.payment_entry.payment_entry as payment_entry
	except ImportError:
		return

	if getattr(payment_entry, "_club_payment_entry_sql_pg_patch", False):
		return

	payment_entry.get_negative_outstanding_invoices = _get_negative_outstanding_invoices_postgres
	payment_entry.get_orders_to_be_billed = _get_orders_to_be_billed_postgres
	payment_entry.get_matched_payment_request_of_references = (
		_get_matched_payment_request_of_references_postgres
	)
	payment_entry._club_payment_entry_sql_pg_patch = True


def _patch_validate_against_pcv() -> None:
	try:
		import erpnext.accounts.general_ledger as general_ledger
	except ImportError:
		return

	if getattr(general_ledger, "_club_validate_pcv_pg_patch", False):
		return

	general_ledger.validate_against_pcv = _validate_against_pcv_postgres
	general_ledger._club_validate_pcv_pg_patch = True


def _patch_delink_original_entry() -> None:
	try:
		import erpnext.accounts.utils as accounts_utils
	except ImportError:
		return

	if getattr(accounts_utils, "_club_delink_original_entry_pg_patch", False):
		return

	accounts_utils.delink_original_entry = _delink_original_entry_postgres
	accounts_utils._club_delink_original_entry_pg_patch = True


def _delink_original_entry_postgres(pl_entry, partial_cancel: bool = False) -> None:
	"""Copia de ERPNext `delink_original_entry` con `delinked=1` (smallint PG)."""
	from erpnext.accounts.utils import is_immutable_ledger_enabled

	if not pl_entry:
		return

	if pl_entry.doctype == "Advance Payment Ledger Entry":
		adv = qb.DocType("Advance Payment Ledger Entry")

		(
			qb.update(adv)
			.set(adv.delinked, 1)
			.set(adv.event, "Cancel")
			.set(adv.modified, now())
			.set(adv.modified_by, frappe.session.user)
			.where(adv.voucher_type == pl_entry.voucher_type)
			.where(adv.voucher_no == pl_entry.voucher_no)
			.where(adv.against_voucher_type == pl_entry.against_voucher_type)
			.where(adv.against_voucher_no == pl_entry.against_voucher_no)
			.where(adv.event == pl_entry.event)
			.run()
		)
		return

	ple = qb.DocType("Payment Ledger Entry")
	query = (
		qb.update(ple)
		.set(ple.modified, now())
		.set(ple.modified_by, frappe.session.user)
		.where(
			(ple.company == pl_entry.company)
			& (ple.account_type == pl_entry.account_type)
			& (ple.account == pl_entry.account)
			& (ple.party_type == pl_entry.party_type)
			& (ple.party == pl_entry.party)
			& (ple.voucher_type == pl_entry.voucher_type)
			& (ple.voucher_no == pl_entry.voucher_no)
			& (ple.against_voucher_type == pl_entry.against_voucher_type)
			& (ple.against_voucher_no == pl_entry.against_voucher_no)
		)
	)

	if partial_cancel:
		query = query.where(ple.voucher_detail_no == pl_entry.voucher_detail_no)

	if not is_immutable_ledger_enabled():
		query = query.set(ple.delinked, 1)

	query.run()


def _patch_held_invoices() -> None:
	"""ERPNext usa CURDATE() (MariaDB); en PostgreSQL es CURRENT_DATE."""
	try:
		import erpnext.accounts.utils as accounts_utils
	except ImportError:
		return

	if getattr(accounts_utils, "_club_held_invoices_pg_patch", False):
		return

	accounts_utils.get_held_invoices = _get_held_invoices_postgres
	accounts_utils._club_held_invoices_pg_patch = True


def _get_held_invoices_postgres(party_type, party):
	held_invoices = None
	if party_type == "Supplier":
		held_invoices = frappe.db.sql(
			"""
			select name from "tabPurchase Invoice"
			where on_hold = 1 and release_date IS NOT NULL and release_date > CURRENT_DATE
			""",
			as_dict=1,
		)
		held_invoices = set(d["name"] for d in held_invoices)
	return held_invoices


def _get_negative_outstanding_invoices_postgres(
	party_type,
	party,
	party_account,
	party_account_currency,
	company_currency,
	cost_center=None,
	condition=None,
):
	"""Copia PG de ERPNext `get_negative_outstanding_invoices` (literales SQL compatibles)."""
	from frappe import scrub

	if party_type not in ["Customer", "Supplier"]:
		return []

	voucher_type = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
	account_col = "debit_to" if voucher_type == "Sales Invoice" else "credit_to"
	supplier_condition = ""
	if voucher_type == "Purchase Invoice":
		supplier_condition = "and (release_date is null or release_date <= CURRENT_DATE)"

	if party_account_currency == company_currency:
		grand_total_field = "base_grand_total"
		rounded_total_field = "base_rounded_total"
	else:
		grand_total_field = "grand_total"
		rounded_total_field = "rounded_total"

	party_field = scrub(party_type)
	condition_sql = condition or ""
	amount_expr = _pg_amount_expr(rounded_total_field, grand_total_field)

	return frappe.db.sql(
		f"""
		select
			%s as voucher_type, name as voucher_no, {account_col} as account,
			{amount_expr} as invoice_amount,
			outstanding_amount, posting_date,
			due_date, conversion_rate as exchange_rate
		from
			"tab{voucher_type}"
		where
			{party_field} = %s and {account_col} = %s and docstatus = 1 and
			outstanding_amount < 0
			{supplier_condition}
			{condition_sql}
		order by
			posting_date, name
		""",
		(voucher_type, party, party_account),
		as_dict=True,
	)


def _get_orders_to_be_billed_postgres(
	posting_date,
	party_type,
	party,
	company,
	party_account_currency,
	company_currency,
	cost_center=None,
	filters=None,
):
	"""Copia PG de ERPNext `get_orders_to_be_billed` (sin función if() MariaDB)."""
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions
	from frappe import scrub

	voucher_type = None
	if party_type == "Customer":
		voucher_type = "Sales Order"
	elif party_type == "Supplier":
		voucher_type = "Purchase Order"

	if not voucher_type:
		return []

	doc = frappe.get_doc({"doctype": voucher_type})
	condition = ""
	if doc and hasattr(doc, "cost_center") and doc.cost_center and cost_center:
		condition = f" and cost_center='{cost_center}'"

	active_dimensions = get_dimensions()[0]
	filters = filters or {}
	for dim in active_dimensions:
		if filters.get(dim.fieldname):
			condition += f" and {dim.fieldname}='{filters.get(dim.fieldname)}'"

	if party_account_currency == company_currency:
		grand_total_field = "base_grand_total"
		rounded_total_field = "base_rounded_total"
	else:
		grand_total_field = "grand_total"
		rounded_total_field = "rounded_total"

	amount_expr = _pg_amount_expr(rounded_total_field, grand_total_field)
	party_field = scrub(party_type)

	orders = frappe.db.sql(
		f"""
		select
			name as voucher_no,
			{amount_expr} as invoice_amount,
			({amount_expr} - advance_paid) as outstanding_amount,
			transaction_date as posting_date
		from
			"tab{voucher_type}"
		where
			{party_field} = %s
			and docstatus = 1
			and company = %s
			and status != 'Closed'
			and {amount_expr} > advance_paid
			and abs(100 - per_billed) > 0.01
			{condition}
		order by
			transaction_date, name
		""",
		(party, company),
		as_dict=True,
	)

	order_list = []
	for d in orders:
		if (
			filters
			and filters.get("outstanding_amt_greater_than")
			and filters.get("outstanding_amt_less_than")
			and not (
				flt(filters.get("outstanding_amt_greater_than"))
				<= flt(d.outstanding_amount)
				<= flt(filters.get("outstanding_amt_less_than"))
			)
		):
			continue

		d["voucher_type"] = voucher_type
		from erpnext.accounts.utils import get_exchange_rate

		d["exchange_rate"] = get_exchange_rate(
			party_account_currency, company_currency, posting_date
		)
		order_list.append(d)

	return order_list


def _get_matched_payment_request_of_references_postgres(references=None):
	"""Copia PG: Min(name) en subquery con GROUP BY (PostgreSQL estricto)."""
	if not references:
		return

	refs = {
		(row.reference_doctype, row.reference_name, row.allocated_amount)
		for row in references
		if row.reference_doctype and row.reference_name and row.allocated_amount
	}

	if not refs:
		return

	pr = frappe.qb.DocType("Payment Request")

	subquery = (
		frappe.qb.from_(pr)
		.select(
			pr.reference_doctype,
			pr.reference_name,
			pr.outstanding_amount.as_("allocated_amount"),
			Min(pr.name).as_("payment_request"),
			Count("*").as_("count"),
		)
		.where(Tuple(pr.reference_doctype, pr.reference_name, pr.outstanding_amount).isin(refs))
		.where(pr.status != "Paid")
		.where(pr.docstatus == 1)
		.groupby(pr.reference_doctype, pr.reference_name, pr.outstanding_amount)
	)

	matched_prs = (
		frappe.qb.from_(subquery)
		.select(
			subquery.reference_doctype,
			subquery.reference_name,
			subquery.allocated_amount,
			subquery.payment_request,
		)
		.where(subquery.count == 1)
		.run()
	)

	return matched_prs if matched_prs else None


def _validate_against_pcv_postgres(is_opening, posting_date, company) -> None:
	if is_opening and frappe.db.exists("Period Closing Voucher", {"docstatus": 1, "company": company}):
		frappe.throw(
			_("Opening Entry can not be created after Period Closing Voucher is created."),
			title=_("Invalid Opening Entry"),
		)

	last_pcv_date = frappe.db.sql(
		"""
		SELECT MAX(period_end_date)
		FROM "tabPeriod Closing Voucher"
		WHERE docstatus = 1 AND company = %s
		""",
		(company,),
	)[0][0]

	if last_pcv_date and getdate(posting_date) <= getdate(last_pcv_date):
		message = _("Books have been closed till the period ending on {0}").format(formatdate(last_pcv_date))
		message += "</br >"
		message += _("You cannot create/amend any accounting entries till this date.")
		frappe.throw(message, title=_("Period Closed"))


def _patch_payment_ledger_query() -> None:
	try:
		from erpnext.accounts.utils import QueryPaymentLedger
	except ImportError:
		return

	if getattr(QueryPaymentLedger, "_club_payment_ledger_pg_patch", False):
		return

	QueryPaymentLedger.query_for_outstanding = _query_for_outstanding_postgres
	QueryPaymentLedger._club_payment_ledger_pg_patch = True


def _query_for_outstanding_postgres(self) -> None:
	"""Copia de ERPNext `query_for_outstanding` con GROUP BY compatible PostgreSQL."""
	ple = self.ple

	filter_on_voucher_no = []
	filter_on_against_voucher_no = []

	if self.vouchers:
		voucher_types = {x.voucher_type for x in self.vouchers}
		voucher_nos = {x.voucher_no for x in self.vouchers}

		filter_on_voucher_no.append(ple.voucher_type.isin(voucher_types))
		filter_on_voucher_no.append(ple.voucher_no.isin(voucher_nos))

		filter_on_against_voucher_no.append(ple.against_voucher_type.isin(voucher_types))
		filter_on_against_voucher_no.append(ple.against_voucher_no.isin(voucher_nos))

	if self.voucher_no:
		filter_on_voucher_no.append(ple.voucher_no.like(f"%{self.voucher_no}%"))
		filter_on_against_voucher_no.append(ple.against_voucher_no.like(f"%{self.voucher_no}%"))

	filter_on_outstanding_amount = []
	if self.min_outstanding:
		if self.min_outstanding > 0:
			filter_on_outstanding_amount.append(
				Table("outstanding").amount_in_account_currency >= self.min_outstanding
			)
		else:
			filter_on_outstanding_amount.append(
				Table("outstanding").amount_in_account_currency <= self.min_outstanding
			)
	if self.max_outstanding:
		if self.max_outstanding > 0:
			filter_on_outstanding_amount.append(
				Table("outstanding").amount_in_account_currency <= self.max_outstanding
			)
		else:
			filter_on_outstanding_amount.append(
				Table("outstanding").amount_in_account_currency >= self.max_outstanding
			)

	if self.limit and self.get_invoices:
		outstanding_vouchers = (
			qb.from_(ple)
			.select(
				ple.against_voucher_no.as_("voucher_no"),
				Sum(ple.amount_in_account_currency).as_("amount_in_account_currency"),
				Max(
					Case().when(
						(
							(ple.voucher_no == ple.against_voucher_no)
							& (ple.voucher_type == ple.against_voucher_type)
						),
						(ple.posting_date),
					)
				).as_("invoice_date"),
			)
			.where(ple.delinked == 0)
			.where(Criterion.all(filter_on_against_voucher_no))
			.where(Criterion.all(self.common_filter))
			.where(Criterion.all(self.dimensions_filter))
			.where(Criterion.all(self.voucher_posting_date))
			.groupby(ple.against_voucher_type, ple.against_voucher_no, ple.party_type, ple.party)
			.orderby(ple.invoice_date, ple.voucher_no)
			.having(Sum(ple.amount_in_account_currency) > 0)
			.limit(self.limit)
			.run()
		)
		if outstanding_vouchers:
			filter_on_voucher_no.append(ple.voucher_no.isin([x[0] for x in outstanding_vouchers]))
			filter_on_against_voucher_no.append(
				ple.against_voucher_no.isin([x[0] for x in outstanding_vouchers])
			)

	query_voucher_amount = (
		qb.from_(ple)
		.select(
			Max(ple.account).as_("account"),
			ple.voucher_type,
			ple.voucher_no,
			ple.party_type,
			ple.party,
			Max(ple.posting_date).as_("posting_date"),
			Max(ple.due_date).as_("due_date"),
			Max(ple.account_currency).as_("currency"),
			Max(ple.cost_center).as_("cost_center"),
			Sum(ple.amount).as_("amount"),
			Sum(ple.amount_in_account_currency).as_("amount_in_account_currency"),
			Max(ple.remarks).as_("remarks"),
		)
		.where(ple.delinked == 0)
		.where(Criterion.all(filter_on_voucher_no))
		.where(Criterion.all(self.common_filter))
		.where(Criterion.all(self.dimensions_filter))
		.where(Criterion.all(self.voucher_posting_date))
		.groupby(ple.voucher_type, ple.voucher_no, ple.party_type, ple.party)
	)

	query_voucher_outstanding = (
		qb.from_(ple)
		.select(
			Max(ple.account).as_("account"),
			ple.against_voucher_type.as_("voucher_type"),
			ple.against_voucher_no.as_("voucher_no"),
			ple.party_type,
			ple.party,
			Max(ple.posting_date).as_("posting_date"),
			Max(ple.due_date).as_("due_date"),
			Max(ple.account_currency).as_("currency"),
			Sum(ple.amount).as_("amount"),
			Sum(ple.amount_in_account_currency).as_("amount_in_account_currency"),
		)
		.where(ple.delinked == 0)
		.where(Criterion.all(filter_on_against_voucher_no))
		.where(Criterion.all(self.common_filter))
		.groupby(ple.against_voucher_type, ple.against_voucher_no, ple.party_type, ple.party)
	)

	self.cte_query_voucher_amount_and_outstanding = (
		qb.with_(query_voucher_amount, "vouchers")
		.with_(query_voucher_outstanding, "outstanding")
		.from_(AliasedQuery("vouchers"))
		.left_join(AliasedQuery("outstanding"))
		.on(
			(AliasedQuery("vouchers").account == AliasedQuery("outstanding").account)
			& (AliasedQuery("vouchers").voucher_type == AliasedQuery("outstanding").voucher_type)
			& (AliasedQuery("vouchers").voucher_no == AliasedQuery("outstanding").voucher_no)
			& (AliasedQuery("vouchers").party_type == AliasedQuery("outstanding").party_type)
			& (AliasedQuery("vouchers").party == AliasedQuery("outstanding").party)
		)
		.select(
			Table("vouchers").account,
			Table("vouchers").voucher_type,
			Table("vouchers").voucher_no,
			Table("vouchers").party_type,
			Table("vouchers").party,
			Table("vouchers").posting_date,
			Table("vouchers").amount.as_("invoice_amount"),
			Table("vouchers").amount_in_account_currency.as_("invoice_amount_in_account_currency"),
			Table("outstanding").amount.as_("outstanding"),
			Table("outstanding").amount_in_account_currency.as_("outstanding_in_account_currency"),
			(Table("vouchers").amount - Table("outstanding").amount).as_("paid_amount"),
			(
				Table("vouchers").amount_in_account_currency
				- Table("outstanding").amount_in_account_currency
			).as_("paid_amount_in_account_currency"),
			Table("vouchers").due_date,
			Table("vouchers").currency,
			Table("vouchers").cost_center.as_("cost_center"),
			Table("vouchers").remarks,
		)
		.where(Criterion.all(filter_on_outstanding_amount))
	)

	if self.limit:
		self.cte_query_voucher_amount_and_outstanding = (
			self.cte_query_voucher_amount_and_outstanding.limit(self.limit)
		)

	self.voucher_outstandings = self.cte_query_voucher_amount_and_outstanding.run(as_dict=True)

	# PostgreSQL no admite HAVING sin GROUP BY (MariaDB sí). ERPNext filtra de nuevo en
	# Python en get_outstanding_invoices; este post-filtro mantiene la semántica.
	if self.get_invoices:
		self.voucher_outstandings = [
			row
			for row in self.voucher_outstandings
			if flt(row.get("outstanding_in_account_currency")) > 0
		]
	elif self.get_payments:
		self.voucher_outstandings = [
			row
			for row in self.voucher_outstandings
			if flt(row.get("outstanding_in_account_currency")) < 0
		]
