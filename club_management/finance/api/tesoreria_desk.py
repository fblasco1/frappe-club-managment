"""API Desk: proyección de flujo de fondos (Tesorería)."""

from __future__ import annotations

import frappe
from frappe.utils import cint

from club_management.finance.permissions import ensure_tesoreria_access
from club_management.finance.services.flujo_fondos import (
	VENTANA_DIAS_DEFAULT,
	calcular_proyeccion_flujo_fondos,
)


@frappe.whitelist()
def get_proyeccion_flujo_fondos(
	as_of_date: str | None = None,
	ventana_dias: int | str | None = None,
) -> dict:
	ensure_tesoreria_access()
	ventana = cint(ventana_dias) if ventana_dias not in (None, "") else VENTANA_DIAS_DEFAULT
	return calcular_proyeccion_flujo_fondos(
		as_of_date=as_of_date or None,
		ventana_dias=ventana,
	)
