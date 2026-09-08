"""Number Cards agregadas sin ORDER BY inválido en PostgreSQL.

Frappe aplica `ORDER BY creation` en consultas SUM/COUNT; PostgreSQL lo rechaza
sin GROUP BY. Workaround vía override_whitelisted_methods (sin tocar frappe).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, flt, now

_SQL_FUNCTION_MAP: dict[str, str] = {
	"Count": "COUNT",
	"Sum": "SUM",
	"Average": "AVG",
	"Minimum": "MIN",
	"Maximum": "MAX",
}


def _parse_filters(
	filters: list | str | None,
	document_type: str,
	to_date: str | None,
) -> list[list[Any]]:
	if not filters:
		parsed: list[list[Any]] = []
	elif isinstance(filters, str):
		parsed = frappe.parse_json(filters)
	else:
		parsed = list(filters)
	if to_date:
		parsed.append([document_type, "creation", "<", to_date])
	return parsed


def _aggregate_list(
	document_type: str,
	*,
	function: str,
	aggregate_field: str,
	filters: list[list[Any]],
	parent_document_type: str | None = None,
) -> float:
	sql_function = _SQL_FUNCTION_MAP[function]
	arg = "*" if sql_function == "COUNT" else aggregate_field
	fields = [{sql_function: arg, "as": "result"}]
	res = frappe.get_list(
		document_type,
		fields=fields,
		filters=filters,
		parent_doctype=parent_document_type,
		order_by=None,
	)
	return flt(res[0]["result"] if res else 0)


@frappe.whitelist()
def get_result(doc: dict | str, filters: list | str | None = None, to_date: str | None = None) -> float:
	doc = frappe.parse_json(doc)
	parsed_filters = _parse_filters(filters, doc["document_type"], to_date)
	return _aggregate_list(
		doc["document_type"],
		function=doc["function"],
		aggregate_field=doc.get("aggregate_function_based_on") or "",
		filters=parsed_filters,
		parent_document_type=doc.get("parent_document_type"),
	)


def _previous_result(card, filters: list | str | None) -> float:
	interval = card.stats_time_interval or "Daily"
	current_date = now()
	if interval == "Daily":
		previous_date = add_to_date(current_date, days=-1)
	elif interval == "Weekly":
		previous_date = add_to_date(current_date, weeks=-1)
	elif interval == "Monthly":
		previous_date = add_to_date(current_date, months=-1)
	else:
		previous_date = add_to_date(current_date, years=-1)

	payload = card.as_dict()
	return get_result(payload, filters, previous_date)


@frappe.whitelist()
def get_percentage_difference(
	doc: dict | str,
	filters: list | str | None = None,
	result: float | str | None = None,
) -> float | None:
	doc = frappe.parse_json(doc)
	result = flt(frappe.parse_json(result))
	card = frappe.get_doc("Number Card", doc["name"])
	if not card.get("show_percentage_stats"):
		return None

	previous_result = _previous_result(card, filters)
	if previous_result == 0:
		return None
	if result == previous_result:
		return 0
	return ((result / previous_result) - 1) * 100.0
