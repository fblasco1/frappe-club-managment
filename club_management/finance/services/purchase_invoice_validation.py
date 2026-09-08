"""Validación server-side de egresos (Purchase Invoice).

Spec: `club_management/specs/flujo_egresos_borrador_aprobacion.md`.

Todo egreso del club debe imputar:
- **Fecha de vencimiento** (`due_date`): necesaria para la proyección de flujo de fondos.
- **Centro de costo** por ítem (`cost_center`): imputación contable obligatoria.

Se ejecuta vía hook `doc_events["Purchase Invoice"]["validate"]` (ver `hooks.py`), por lo
que aplica tanto en Borrador como al Presentar.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def validate_egreso(doc: Any, method: str | None = None) -> None:
	"""Exige due_date y centro de costo en cada ítem de la factura de compra."""
	if not doc.get("due_date"):
		frappe.throw(
			_("Debe indicar la Fecha de Vencimiento del egreso."),
			frappe.ValidationError,
		)

	for item in doc.get("items") or []:
		if not item.get("cost_center"):
			descripcion = item.get("item_code") or item.get("item_name") or item.get("idx")
			frappe.throw(
				_("El ítem {0} debe tener un Centro de Costo.").format(descripcion),
				frappe.ValidationError,
			)
