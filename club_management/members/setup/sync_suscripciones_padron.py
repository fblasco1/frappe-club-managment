"""Sincroniza suscripciones del padrón y opcionalmente genera deuda mensual.

Ejemplo:

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.members.setup.sync_suscripciones_padron.run \\
        --kwargs '{"generar_deuda": True, "reference_date": "2026-07-01"}'
"""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe.utils import getdate, today

from club_management.members.services.cobranza_periodica import (
	generar_deuda_mensual_socios,
	socios_elegibles_deuda_mensual,
)
from club_management.members.services.suscripciones_socio import sync_suscripciones_socio


def _first_day_of_month(reference: str | date | None = None) -> date:
	d = getdate(reference or today())
	return date(d.year, d.month, 1)


def run(
	*,
	generar_deuda: bool = True,
	reference_date: str | None = None,
	solo_socios: list[str] | None = None,
) -> dict[str, Any]:
	"""Sincroniza suscripciones cuota+arancel y genera deuda del período."""
	ref = _first_day_of_month(reference_date)
	socios = solo_socios or socios_elegibles_deuda_mensual()

	sync_ok: list[str] = []
	sync_err: list[dict[str, str]] = []
	for socio_name in socios:
		try:
			sync_suscripciones_socio(socio_name)
			sync_ok.append(socio_name)
		except Exception as exc:
			sync_err.append({"socio": socio_name, "error": str(exc)})
			frappe.log_error(
				title=f"Sync suscripción — {socio_name}",
				message=frappe.get_traceback(),
			)

	result: dict[str, Any] = {
		"reference_date": str(ref),
		"socios_sincronizados": len(sync_ok),
		"sync_errores": sync_err,
	}
	if generar_deuda:
		result["deuda"] = generar_deuda_mensual_socios(reference_date=ref)
	return result
