"""Operaciones batch — complementar aranceles de un período."""

from __future__ import annotations

import frappe
from frappe.utils import getdate

from club_management.members.services.cobranza_manual import build_invoice_items_for_socio, format_periodo_cobro
from club_management.members.services.cobranza_periodica import (
	complementar_aranceles_periodo_socios,
	socios_elegibles_deuda_mensual,
)


def run(reference_date: str = "2026-07-01", dry_run: bool = False) -> dict:
	"""Emite aranceles faltantes del período para socios elegibles."""
	frappe.only_for(("System Manager", "Secretaria"))
	ref = getdate(reference_date)
	periodo = format_periodo_cobro(ref)

	if dry_run:
		pendientes: list[str] = []
		for socio_name in socios_elegibles_deuda_mensual():
			items = build_invoice_items_for_socio(
				socio_name,
				incluir_actividades=True,
				incluir_cargos_extra=False,
				solo_aranceles=True,
				reference_date=str(ref),
				periodo_cobro=periodo,
			)
			if items:
				pendientes.append(socio_name)
		result = {
			"dry_run": True,
			"periodo": periodo,
			"reference_date": str(ref),
			"socios_con_aranceles_pendientes": len(pendientes),
			"socios_muestra": pendientes[:30],
		}
		frappe.msgprint(frappe.as_json(result, indent=2))
		return result

	result = complementar_aranceles_periodo_socios(reference_date=ref)
	frappe.msgprint(frappe.as_json(result, indent=2))
	return result
