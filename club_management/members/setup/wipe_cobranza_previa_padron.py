"""Elimina facturas y pagos de prueba anteriores al corte del padrón definitivo.

Ejemplo (simulación):

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.members.setup.wipe_cobranza_previa_padron.run \\
        --kwargs '{"dry_run": True, "cutoff_invoice": "ACC-SINV-2026-00011"}'

Ejecución real:

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.members.setup.wipe_cobranza_previa_padron.run \\
        --kwargs '{"dry_run": False, "confirm": "WIPE_COBRANZA_PREVIA", "cutoff_invoice": "ACC-SINV-2026-00011"}'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _

from club_management.members.services.cobranza_manual import sync_saldo_deuda_socio
from club_management.members.setup.wipe_socios_prueba import (
	PAYMENT_ENTRY_DOCTYPE,
	SALES_INVOICE_DOCTYPE,
	_delete_docs,
)

CONFIRM_TOKEN = "WIPE_COBRANZA_PREVIA"
DEFAULT_CUTOFF = "ACC-SINV-2026-00011"


@dataclass
class WipeCobranzaStats:
	cutoff_invoice: str = ""
	sales_invoices: int = 0
	payment_entries: int = 0
	cargo_socio_desvinculados: int = 0
	socios_saldo_resincronizado: int = 0
	errors: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"cutoff_invoice": self.cutoff_invoice,
			"sales_invoices": self.sales_invoices,
			"payment_entries": self.payment_entries,
			"cargo_socio_desvinculados": self.cargo_socio_desvinculados,
			"socios_saldo_resincronizado": self.socios_saldo_resincronizado,
			"errors": self.errors,
		}


def run(
	*,
	dry_run: bool = True,
	confirm: str = "",
	cutoff_invoice: str = DEFAULT_CUTOFF,
) -> dict[str, Any]:
	if not cutoff_invoice:
		frappe.throw(_("cutoff_invoice es obligatorio."))

	if not dry_run and confirm != CONFIRM_TOKEN:
		frappe.throw(
			_(
				"Para borrar datos reales pase confirm='{0}' y dry_run=False."
			).format(CONFIRM_TOKEN)
		)

	stats = wipe_cobranza_previa(cutoff_invoice=cutoff_invoice, dry_run=dry_run)
	_print_resumen(stats, dry_run=dry_run)
	if not dry_run:
		frappe.db.commit()
	return stats.to_dict()


def wipe_cobranza_previa(*, cutoff_invoice: str, dry_run: bool = True) -> WipeCobranzaStats:
	stats = WipeCobranzaStats(cutoff_invoice=cutoff_invoice)

	if not frappe.db.exists("DocType", SALES_INVOICE_DOCTYPE):
		return stats

	si_names = _sales_invoices_before(cutoff_invoice)
	pe_names = _payment_entries_for_invoices(si_names)
	socios_afectados = _socios_en_facturas(si_names)

	stats.sales_invoices = len(si_names)
	stats.payment_entries = len(pe_names)
	stats.cargo_socio_desvinculados = _count_cargo_socio_vinculados(si_names)
	stats.socios_saldo_resincronizado = len(socios_afectados)

	if dry_run:
		return stats

	frappe.db.rollback()
	_delete_docs(PAYMENT_ENTRY_DOCTYPE, pe_names, stats)
	_desvincular_cargo_socio(si_names, stats)
	_delete_docs(SALES_INVOICE_DOCTYPE, si_names, stats)

	for socio in socios_afectados:
		try:
			sync_saldo_deuda_socio(socio)
		except Exception as exc:  # noqa: BLE001
			stats.errors.append(f"sync saldo {socio}: {exc}")

	return stats


def _sales_invoices_before(cutoff_invoice: str) -> list[str]:
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"name": ["<", cutoff_invoice]},
		pluck="name",
		order_by="name asc",
	)


def _payment_entries_for_invoices(si_names: list[str]) -> list[str]:
	if not si_names or not frappe.db.exists("DocType", PAYMENT_ENTRY_DOCTYPE):
		return []

	candidates = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", si_names],
		},
		pluck="parent",
		distinct=True,
	)

	safe: list[str] = []
	si_set = set(si_names)
	for pe_name in candidates:
		refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": pe_name, "reference_doctype": SALES_INVOICE_DOCTYPE},
			pluck="reference_name",
		)
		if refs and all(ref in si_set for ref in refs):
			safe.append(pe_name)
	return sorted(set(safe))


def _socios_en_facturas(si_names: list[str]) -> list[str]:
	if not si_names:
		return []
	meta = frappe.get_meta(SALES_INVOICE_DOCTYPE)
	socios: set[str] = set()
	if meta.has_field("socio"):
		for name in frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={"name": ["in", si_names], "socio": ["is", "set"]},
			pluck="socio",
		):
			if name:
				socios.add(name)
	if meta.has_field("customer"):
		customer_names = frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={"name": ["in", si_names], "customer": ["is", "set"]},
			pluck="customer",
			distinct=True,
		)
		if customer_names and frappe.get_meta("Customer").has_field("socio"):
			for socio in frappe.get_all(
				"Customer",
				filters={"name": ["in", customer_names], "socio": ["is", "set"]},
				pluck="socio",
			):
				if socio:
					socios.add(socio)
	return sorted(socios)


def _count_cargo_socio_vinculados(si_names: list[str]) -> int:
	if not si_names or not frappe.db.exists("DocType", "Cargo Socio"):
		return 0
	if not frappe.get_meta("Cargo Socio").has_field("sales_invoice"):
		return 0
	return frappe.db.count("Cargo Socio", {"sales_invoice": ["in", si_names]})


def _desvincular_cargo_socio(si_names: list[str], stats: WipeCobranzaStats) -> None:
	if not si_names or not frappe.db.exists("DocType", "Cargo Socio"):
		return
	if not frappe.get_meta("Cargo Socio").has_field("sales_invoice"):
		return
	for name in frappe.get_all(
		"Cargo Socio",
		filters={"sales_invoice": ["in", si_names]},
		pluck="name",
	):
		try:
			frappe.db.set_value("Cargo Socio", name, "sales_invoice", None, update_modified=False)
			if frappe.get_meta("Cargo Socio").has_field("estado"):
				frappe.db.set_value("Cargo Socio", name, "estado", "Pendiente", update_modified=False)
		except Exception as exc:  # noqa: BLE001
			stats.errors.append(f"Cargo Socio {name}: {exc}")


def _print_resumen(stats: WipeCobranzaStats, *, dry_run: bool = True) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "BORRADO EJECUTADO"
	print("\n" + "=" * 72)
	print(f" WIPE COBRANZA PREVIA PADRÓN — {mode}")
	print("=" * 72)
	for label, value in stats.to_dict().items():
		if label == "errors":
			continue
		print(f" {label:30s}: {value}")
	if stats.errors:
		print("-" * 72)
		print(" Errores:")
		for err in stats.errors[:20]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
