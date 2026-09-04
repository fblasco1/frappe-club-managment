"""Repara líneas SI del concepto SUPERIOR B facturadas como vóley federado.

Spec: `club_management/specs/pagos_por_equipo.md`
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_MASCULINO_SUPERIOR_AMARILLO,
)

_WRONG_ITEM = "ICDPE-VOLEY-FEDERADO"


def inventariar_si_superior_b_mal_etiquetadas() -> list[dict[str, Any]]:
	"""Líneas SI con ítem vóley ligadas a PE cuyo reference_no contiene SUPERIOR B."""
	return frappe.db.sql(
		"""
		SELECT DISTINCT sii.name AS sii_name, si.name AS si_name, si.socio,
		       pe.name AS pe_name, pe.reference_no, sii.item_code, sii.amount
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
		INNER JOIN `tabPayment Entry Reference` per
			ON per.reference_name = si.name AND per.reference_doctype = 'Sales Invoice'
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
		WHERE sii.item_code = %s
		  AND pe.reference_no ILIKE %s
		ORDER BY si.socio, si.name
		""",
		(_WRONG_ITEM, "%SUPERIOR B%"),
		as_dict=True,
	)


def reparar_si_superior_b_mal_etiquetadas(*, dry_run: bool = True) -> dict[str, Any]:
	"""Cambia ítem de línea a `BASQUET / SUPERIOR / AMARILLO`."""
	rows = inventariar_si_superior_b_mal_etiquetadas()
	updated = 0
	if not dry_run:
		for row in rows:
			frappe.db.set_value(
				"Sales Invoice Item",
				row.sii_name,
				"item_code",
				ITEM_MASCULINO_SUPERIOR_AMARILLO,
				update_modified=False,
			)
			updated += 1
		frappe.clear_cache(doctype="Sales Invoice")
	return {
		"dry_run": dry_run,
		"candidatas": len(rows),
		"actualizadas": updated,
		"sample": rows[:10],
	}


def run_local_apply() -> dict[str, Any]:
	return reparar_si_superior_b_mal_etiquetadas(dry_run=False)


def run_prod_apply() -> dict[str, Any]:
	return reparar_si_superior_b_mal_etiquetadas(dry_run=False)
