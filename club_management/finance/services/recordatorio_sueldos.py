"""Recordatorio mensual de provisión de sueldos (último día hábil)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, get_last_day, getdate, today

PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"


@dataclass(frozen=True)
class ProvisionSueldoSpec:
	key: str
	label: str
	supplier_name: str
	item_code: str


PROVISION_SUELDOS: tuple[ProvisionSueldoSpec, ...] = (
	ProvisionSueldoSpec(
		"sueldos",
		"Sueldos del personal",
		"ICDPE-Sueldos Personal",
		"ICDPE-FIN-SUELDOS",
	),
	ProvisionSueldoSpec(
		"cargas_931",
		"Formulario 931 / cargas sociales",
		"ICDPE-AFIP 931",
		"ICDPE-FIN-CARGAS-931",
	),
	ProvisionSueldoSpec(
		"art",
		"ART",
		"ICDPE-ART",
		"ICDPE-FIN-ART",
	),
	ProvisionSueldoSpec(
		"utedyc",
		"Aportes UTEDYC",
		"ICDPE-UTEDYC",
		"ICDPE-FIN-UTEDYC",
	),
	ProvisionSueldoSpec(
		"entrenadores",
		"Honorarios entrenadores / profesores",
		"ICDPE-Sueldos Personal",
		"ICDPE-FIN-ENTRENADORES",
	),
)


def get_ultimo_dia_habil_mes(reference_date: str | date) -> date:
	"""Último día lun–vie del mes de `reference_date` (sin feriados en MVP)."""
	ref = getdate(reference_date)
	ultimo = getdate(get_last_day(ref))
	while ultimo.weekday() >= 5:
		ultimo = getdate(add_days(ultimo, -1))
	return ultimo


def is_ultimo_dia_habil(reference_date: str | date | None = None) -> bool:
	ref = getdate(reference_date or today())
	return ref == get_ultimo_dia_habil_mes(ref)


def _resolve_supplier_name(supplier_name: str) -> str | None:
	if frappe.db.exists("Supplier", supplier_name):
		return supplier_name
	return frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")


def _item_facturado_en_mes(item_code: str, mes_inicio: date, mes_fin: date) -> bool:
	if not frappe.db.exists("DocType", PURCHASE_INVOICE_DOCTYPE):
		return False
	rows = frappe.db.sql(
		"""
		SELECT 1
		FROM "tabPurchase Invoice" pi
		INNER JOIN "tabPurchase Invoice Item" pii ON pii.parent = pi.name
		WHERE pi.docstatus = 1
			AND pii.item_code = %s
			AND pi.posting_date BETWEEN %s AND %s
		LIMIT 1
		""",
		(item_code, mes_inicio, mes_fin),
	)
	return bool(rows)


def get_conceptos_pendientes_provision(
	reference_date: str | date | None = None,
) -> list[dict[str, Any]]:
	"""Conceptos de sueldo sin PI submitted en el mes."""
	ref = getdate(reference_date or today())
	mes_inicio = getdate(get_first_day(ref))
	mes_fin = getdate(get_last_day(ref))
	pendientes: list[dict[str, Any]] = []

	for spec in PROVISION_SUELDOS:
		if _item_facturado_en_mes(spec.item_code, mes_inicio, mes_fin):
			continue
		supplier = _resolve_supplier_name(spec.supplier_name)
		pendientes.append(
			{
				"key": spec.key,
				"label": spec.label,
				"supplier": supplier or spec.supplier_name,
				"supplier_label": spec.supplier_name,
				"item_code": spec.item_code,
				"club_concepto": "Personal",
			}
		)
	return pendientes


def get_recordatorio_provision_sueldos_payload(
	reference_date: str | date | None = None,
) -> dict[str, Any]:
	"""Payload para banner del panel Secretaría."""
	ref = getdate(reference_date or today())
	ultimo_habil = get_ultimo_dia_habil_mes(ref)
	es_ultimo = ref == ultimo_habil

	if not es_ultimo:
		return {
			"mostrar": False,
			"es_ultimo_dia_habil": False,
			"fecha_referencia": str(ref),
			"ultimo_dia_habil": str(ultimo_habil),
			"conceptos_pendientes": [],
			"mensaje": "",
		}

	pendientes = get_conceptos_pendientes_provision(ref)
	if pendientes:
		mensaje = _(
			"Hoy es el último día hábil del mes: cargá la Purchase Invoice de provisión para cada concepto pendiente."
		)
	else:
		mensaje = _("Provisión de sueldos del mes completa. No hay conceptos pendientes.")

	return {
		"mostrar": True,
		"es_ultimo_dia_habil": True,
		"fecha_referencia": str(ref),
		"ultimo_dia_habil": str(ultimo_habil),
		"conceptos_pendientes": pendientes,
		"mensaje": mensaje,
		"nueva_factura_compra_route": "/app/purchase-invoice/new",
	}
