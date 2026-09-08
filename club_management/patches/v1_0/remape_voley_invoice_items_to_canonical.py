"""Remapea facturas Vóley legacy (TIRA/ESCUELITA) → FEDERADO/ESCUELA.

Completa el consolidate: Links de estructura ya estaban canónicos; faltaban
las líneas de Sales Invoice Item.
"""

from __future__ import annotations

import frappe

from club_management.activities.services.voley_icdpe_items import (
	consolidate_voley_escuela_federado,
	remape_voley_sales_invoice_items,
)


def execute() -> None:
	result_si = remape_voley_sales_invoice_items()
	result = consolidate_voley_escuela_federado()
	frappe.logger("club_management").info(
		"remape_voley_invoice_items_to_canonical: si=%s consolidate=%s",
		result_si,
		{k: result.get(k) for k in ("remap_sales_invoice_items", "retired", "deleted")},
	)
