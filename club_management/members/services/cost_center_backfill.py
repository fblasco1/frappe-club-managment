"""Re-asignación de centro de costo en facturas de venta ya emitidas.

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.

Corrige facturas históricas cuyas líneas de arancel quedaron imputadas al centro
de costo por defecto de la empresa en lugar del centro de costo de la actividad
(`Item Default.selling_cost_center`). Actualiza la línea (`Sales Invoice Item`) y
repone los asientos (`GL Entry`) del ingreso, replicando el mecanismo de
"Repost Accounting Ledger" de ERPNext.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from club_management.members.services.cobranza_manual import resolve_cost_center_item

SALES_INVOICE = "Sales Invoice"


def _facturas_con_cost_center_desalineado() -> list[str]:
	"""Facturas (docstatus=1) con al menos una línea cuyo CC != CC del ítem."""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT sii.parent
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
		JOIN `tabItem Default` idf
			ON idf.parent = sii.item_code AND idf.company = si.company
		WHERE COALESCE(idf.selling_cost_center, '') != ''
			AND COALESCE(sii.cost_center, '') != idf.selling_cost_center
		""",
		as_dict=True,
	)
	return [r["parent"] for r in rows]


def _repost_gl_entries(invoice: "frappe.model.document.Document") -> None:
	"""Reversa y regenera los asientos de la factura con los CC actualizados."""
	frappe.flags.through_repost_accounting_ledger = True
	invoice.docstatus = 2
	invoice.make_gl_entries_on_cancel(from_repost=True)
	invoice.docstatus = 1
	if hasattr(invoice, "force_set_against_income_account"):
		invoice.force_set_against_income_account()
	invoice.make_gl_entries()


def reasignar_cost_center_aranceles(
	invoice_names: list[str] | None = None,
) -> dict[str, Any]:
	"""Re-imputa el centro de costo de las líneas según el `Item Default` del ítem.

	Si `invoice_names` es `None`, procesa todas las facturas con centro de costo
	desalineado. Devuelve un resumen de ejecución.
	"""
	nombres = invoice_names if invoice_names is not None else _facturas_con_cost_center_desalineado()

	# El repost de GL reversa entradas del Payment Ledger (`delinked=true`), que en
	# PostgreSQL requiere el monkeypatch de compatibilidad del proyecto.
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()

	facturas_actualizadas = 0
	lineas_actualizadas = 0
	errores: list[dict[str, str]] = []

	for name in nombres:
		try:
			invoice = frappe.get_doc(SALES_INVOICE, name)
			cambiada = False
			for fila in invoice.items:
				destino = resolve_cost_center_item(fila.item_code, invoice.company)
				if destino and fila.cost_center != destino:
					frappe.db.set_value(
						"Sales Invoice Item",
						fila.name,
						"cost_center",
						destino,
						update_modified=False,
					)
					fila.cost_center = destino
					lineas_actualizadas += 1
					cambiada = True

			if not cambiada:
				continue

			if invoice.docstatus == 1:
				_repost_gl_entries(invoice)
			facturas_actualizadas += 1
		except Exception as exc:  # noqa: BLE001
			errores.append({"factura": name, "error": str(exc)})
			frappe.log_error(
				title=_("Reasignación CC — error en factura {0}").format(name),
				message=frappe.get_traceback(),
			)

	resultado = {
		"facturas_evaluadas": len(nombres),
		"facturas_actualizadas": facturas_actualizadas,
		"lineas_actualizadas": lineas_actualizadas,
		"errores": len(errores),
		"detalle_errores": errores,
	}
	frappe.logger("club_management.cobranza").info(
		"reasignar_cost_center_aranceles %s", resultado
	)
	return resultado
