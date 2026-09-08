"""Servicio de datos del panel operativo de Tesorería (GF-6).

Arma las tres listas del panel con plan de cuenta y centro de costo:
- Facturas de compra en Borrador pendientes de aprobación (PAGOS PENDIENTES).
- Facturas de compra pagas en el último mes.
- Cobros recibidos en el último mes (cuenta/centro tomados de la factura de venta).

Incluye un resumen de liquidez a 5 días (`calcular_proyeccion_flujo_fondos`)
para el número de un saque del Tesorero, sin abrir el Script Report.

El acceso está restringido por `ensure_finance_panel_access` (Tesorería/Secretaría).
Las consultas son de alcance club-wide (no hay datos por-socio), por lo que el
gate por rol es suficiente para el aislamiento. La proyección se calcula con
`skip_permission_check=True` **después** de ese gate, para que Secretaría
también vea el número (el Script Report sigue exigiendo Tesoreria).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_months, fmt_money, format_date, getdate, nowdate

from club_management.finance.permissions import ensure_finance_panel_access
from club_management.finance.services.flujo_fondos import (
	VENTANA_DIAS_DEFAULT,
	calcular_proyeccion_flujo_fondos,
)
from club_management.finance.services.informes_contables import informes_contables_panel

LIMIT = 5


def get_panel_data() -> dict:
	"""Devuelve las listas del panel de Tesorería (con gate de acceso)."""
	ensure_finance_panel_access()
	return {
		"liquidez": _liquidez_resumen(),
		"informes_contables": informes_contables_panel(),
		"borradores_pendientes": facturas_compra_borrador(),
		"facturas_pagas": facturas_compra_pagas_ultimo_mes(),
		"cobros_recibidos": cobros_recibidos_ultimo_mes(),
	}


def _liquidez_resumen() -> dict | None:
	"""Liquidez a N días y gastos en borrador. None si ERPNext no está."""
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return None
	try:
		proy = calcular_proyeccion_flujo_fondos(
			ventana_dias=VENTANA_DIAS_DEFAULT,
			skip_permission_check=True,
		)
	except frappe.ValidationError:
		return None
	return {
		"ventana_dias": proy["ventana_dias"],
		"as_of_date": proy["as_of_date"],
		"liquidez_proyectada": proy["liquidez_proyectada"],
		"liquidez_proyectada_label": _money(proy["liquidez_proyectada"]),
		"gastos_proyectados_pendientes": proy["gastos_proyectados_pendientes"],
		"gastos_proyectados_pendientes_label": _money(
			proy["gastos_proyectados_pendientes"]
		),
		"liquidez_alcanza": proy["liquidez_alcanza"],
	}


def _currency() -> str:
	return frappe.defaults.get_global_default("currency") or "ARS"


def _money(value: float | int | None) -> str:
	return fmt_money(value or 0, currency=_currency())


def _fecha(value) -> str:
	return format_date(value) if value else ""


def _cuenta_centro_por_item(
	child_doctype: str, parents: list[str], account_field: str
) -> dict[str, dict[str, str]]:
	"""Agrega, por documento padre, las cuentas y centros de costo distintos de sus ítems."""
	if not parents:
		return {}
	rows = frappe.get_all(
		child_doctype,
		filters={"parent": ["in", parents]},
		fields=["parent", f"{account_field} as cuenta", "cost_center"],
	)
	agg: dict[str, dict[str, set]] = {}
	for row in rows:
		entry = agg.setdefault(row.parent, {"cuentas": set(), "centros": set()})
		if row.cuenta:
			entry["cuentas"].add(row.cuenta)
		if row.cost_center:
			entry["centros"].add(row.cost_center)
	return {
		parent: {
			"cuenta": ", ".join(sorted(v["cuentas"])),
			"centro_costo": ", ".join(sorted(v["centros"])),
		}
		for parent, v in agg.items()
	}


def _fila(
	*,
	doctype: str,
	name: str,
	titulo: str,
	importe: float | int | None,
	fecha,
	estado: str,
	cuenta_centro: dict[str, dict[str, str]],
	cuenta_fallback: str = "",
) -> dict:
	cc = cuenta_centro.get(name, {})
	return {
		"doctype": doctype,
		"name": name,
		"titulo": titulo or name,
		"importe": importe or 0,
		"importe_label": _money(importe),
		"fecha_label": _fecha(fecha),
		"estado": estado or "",
		"cuenta": cc.get("cuenta") or cuenta_fallback,
		"centro_costo": cc.get("centro_costo") or "",
	}


def facturas_compra_borrador() -> list[dict]:
	"""Facturas de compra en Borrador (docstatus=0) pendientes de aprobación."""
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return []
	facturas = frappe.get_all(
		"Purchase Invoice",
		filters={"docstatus": 0},
		fields=["name", "supplier", "supplier_name", "due_date", "grand_total"],
		order_by="due_date asc",
		limit=LIMIT,
	)
	cc = _cuenta_centro_por_item(
		"Purchase Invoice Item", [f.name for f in facturas], "expense_account"
	)
	return [
		_fila(
			doctype="Purchase Invoice",
			name=f.name,
			titulo=f.supplier_name or f.supplier,
			importe=f.grand_total,
			fecha=f.due_date,
			estado="Borrador",
			cuenta_centro=cc,
		)
		for f in facturas
	]


def facturas_compra_pagas_ultimo_mes() -> list[dict]:
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return []
	desde = add_months(getdate(nowdate()), -1)
	facturas = frappe.get_all(
		"Purchase Invoice",
		filters={"docstatus": 1, "status": "Paid", "posting_date": [">=", desde]},
		fields=["name", "supplier", "supplier_name", "posting_date", "grand_total", "status"],
		order_by="posting_date desc",
		limit=LIMIT,
	)
	cc = _cuenta_centro_por_item(
		"Purchase Invoice Item", [f.name for f in facturas], "expense_account"
	)
	return [
		_fila(
			doctype="Purchase Invoice",
			name=f.name,
			titulo=f.supplier_name or f.supplier,
			importe=f.grand_total,
			fecha=f.posting_date,
			estado=f.status,
			cuenta_centro=cc,
		)
		for f in facturas
	]


def cobros_recibidos_ultimo_mes() -> list[dict]:
	if not frappe.db.exists("DocType", "Payment Entry"):
		return []
	desde = add_months(getdate(nowdate()), -1)
	cobros = frappe.get_all(
		"Payment Entry",
		filters={"docstatus": 1, "payment_type": "Receive", "posting_date": [">=", desde]},
		fields=["name", "party", "party_name", "posting_date", "paid_amount", "paid_to"],
		order_by="posting_date desc",
		limit=LIMIT,
	)
	if not cobros:
		return []

	# Facturas de venta referenciadas en cada cobro.
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"parent": ["in", [c.name for c in cobros]],
			"reference_doctype": "Sales Invoice",
		},
		fields=["parent", "reference_name"],
	)
	pe_a_facturas: dict[str, list[str]] = {}
	todas_facturas: set[str] = set()
	for ref in refs:
		pe_a_facturas.setdefault(ref.parent, []).append(ref.reference_name)
		todas_facturas.add(ref.reference_name)

	cc_facturas = _cuenta_centro_por_item(
		"Sales Invoice Item", list(todas_facturas), "income_account"
	)

	filas = []
	for c in cobros:
		cuentas: set[str] = set()
		centros: set[str] = set()
		for factura in pe_a_facturas.get(c.name, []):
			datos = cc_facturas.get(factura, {})
			if datos.get("cuenta"):
				cuentas.update(datos["cuenta"].split(", "))
			if datos.get("centro_costo"):
				centros.update(datos["centro_costo"].split(", "))
		cuenta_centro = {c.name: {"cuenta": ", ".join(sorted(cuentas)), "centro_costo": ", ".join(sorted(centros))}}
		filas.append(
			_fila(
				doctype="Payment Entry",
				name=c.name,
				titulo=c.party_name or c.party or c.name,
				importe=c.paid_amount,
				fecha=c.posting_date,
				estado="",
				cuenta_centro=cuenta_centro,
				cuenta_fallback=c.paid_to or "",
			)
		)
	return filas
