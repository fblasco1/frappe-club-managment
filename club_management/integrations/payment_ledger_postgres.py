"""Compatibilidad ERPNext + PostgreSQL (sin modificar erpnext).

- Payment Ledger: GROUP BY estricto en consultas de saldo.
- Period Closing Voucher: MAX sin ORDER BY inválido en get_value.
- Cancelación de facturas: `delinked`/`is_cancelled` como smallint, no boolean.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, now, flt
from frappe import qb
from frappe.query_builder import AliasedQuery, Case, Criterion, Table
from frappe.query_builder.functions import Max, Sum


def apply_patch() -> None:
	"""Idempotente; solo aplica en sitios PostgreSQL con ERPNext."""
	if frappe.db.db_type != "postgres":
		return

	_patch_payment_ledger_query()
	_patch_validate_against_pcv()
	_patch_delink_original_entry()


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
			ple.account,
			ple.voucher_type,
			ple.voucher_no,
			ple.party_type,
			ple.party,
			ple.posting_date,
			ple.due_date,
			ple.account_currency.as_("currency"),
			ple.cost_center.as_("cost_center"),
			Sum(ple.amount).as_("amount"),
			Sum(ple.amount_in_account_currency).as_("amount_in_account_currency"),
			ple.remarks,
		)
		.where(ple.delinked == 0)
		.where(Criterion.all(filter_on_voucher_no))
		.where(Criterion.all(self.common_filter))
		.where(Criterion.all(self.dimensions_filter))
		.where(Criterion.all(self.voucher_posting_date))
		.groupby(
			ple.account,
			ple.voucher_type,
			ple.voucher_no,
			ple.party_type,
			ple.party,
			ple.posting_date,
			ple.due_date,
			ple.account_currency,
			ple.cost_center,
			ple.remarks,
		)
	)

	query_voucher_outstanding = (
		qb.from_(ple)
		.select(
			ple.account,
			ple.against_voucher_type.as_("voucher_type"),
			ple.against_voucher_no.as_("voucher_no"),
			ple.party_type,
			ple.party,
			ple.posting_date,
			ple.due_date,
			ple.account_currency.as_("currency"),
			Sum(ple.amount).as_("amount"),
			Sum(ple.amount_in_account_currency).as_("amount_in_account_currency"),
		)
		.where(ple.delinked == 0)
		.where(Criterion.all(filter_on_against_voucher_no))
		.where(Criterion.all(self.common_filter))
		.groupby(
			ple.account,
			ple.against_voucher_type,
			ple.against_voucher_no,
			ple.party_type,
			ple.party,
			ple.posting_date,
			ple.due_date,
			ple.account_currency,
		)
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
