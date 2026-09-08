"""Catálogo de Items financieros ICDPE (ingresos eventuales + egresos).

Egresos: 4 pilares bajo ``All Item Groups`` con subgrupos hoja para Secretaría /
Tesorería (Flujo de Fondos). Seed idempotente; no borra ítems legacy (los
deshabilita).
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe

from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.finance.setup.icdpe_income_item_groups import (
	INGRESO_LEAF_GROUPS,
	INGRESO_PILLARS,
	LEAF_ALQUILERES,
	LEAF_DONACIONES,
	LEAF_ENTRADAS,
	LEAF_GASTRONOMIA,
	LEAF_RECAUDACION,
	LEAF_SPONSORS,
	LEAF_SUBSIDIOS,
	ensure_ingresos_item_group_tree,
)

DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"

ADMIN_CC = "Administración - ICDPE"
BUFFET_CC = "Buffet - ICDPE"
RESTAURANTE_CC = "Restaurante - ICDPE"
ALQUILER_TEMP_CC = "Temporal - ICDPE"
BASQUET_CC = "Basquet - ICDPE"

# --- 4 pilares centrales (is_group = 1) ---
CENTRAL_ESTRUCTURA = "Gastos de Estructura y Servicios"
CENTRAL_PERSONAL = "Gastos de Personal (Nómina)"
CENTRAL_DEPORTIVOS = "Costos Operativos Deportivos"
CENTRAL_MANTENIMIENTO = "Mantenimiento e Infraestructura"

EGRESO_CENTRAL_GROUPS: tuple[str, ...] = (
	CENTRAL_ESTRUCTURA,
	CENTRAL_PERSONAL,
	CENTRAL_DEPORTIVOS,
	CENTRAL_MANTENIMIENTO,
)

# --- Subgrupos hoja (is_group = 0; reciben Items) ---
GROUP_SERVICIOS_PUB = "Servicios Públicos"
GROUP_IMPUESTOS = "Impuestos y Tasas"
# Extra bajo Estructura: RC / emergencias / accidentes.
GROUP_SEGUROS = "Seguros y Coberturas"

GROUP_REMUNERACIONES = "Remuneraciones y Sueldos"
GROUP_CARGAS = "Cargas Sociales y Contribuciones Patronales"

GROUP_HONORARIOS = "Honorarios y Servicios Profesionales"
GROUP_FEDERATIVOS = "Afiliaciones y Aranceles Federativos"
GROUP_INSUMOS = "Insumos y Materiales Deportivos"

GROUP_REPARACIONES = "Reparaciones y Repuestos"
GROUP_OBRAS = "Obras y Materiales"

# central → hojas
EGRESO_TREE: dict[str, tuple[str, ...]] = {
	CENTRAL_ESTRUCTURA: (GROUP_SERVICIOS_PUB, GROUP_IMPUESTOS, GROUP_SEGUROS),
	CENTRAL_PERSONAL: (GROUP_REMUNERACIONES, GROUP_CARGAS),
	CENTRAL_DEPORTIVOS: (GROUP_HONORARIOS, GROUP_FEDERATIVOS, GROUP_INSUMOS),
	CENTRAL_MANTENIMIENTO: (GROUP_REPARACIONES, GROUP_OBRAS),
}

EGRESO_LEAF_GROUPS: tuple[str, ...] = tuple(
	leaf for leaves in EGRESO_TREE.values() for leaf in leaves
)

# Ítems genéricos del catálogo plano previo — se deshabilitan (no se borran).
LEGACY_EXPENSE_ITEMS_TO_DISABLE: tuple[str, ...] = (
	"ICDPE-FIN-SUELDOS",
	"ICDPE-FIN-IMPUESTOS",
	"ICDPE-FIN-FEDERACION",
	"ICDPE-FIN-INSUMOS-DEP",
	"ICDPE-FIN-MANT-IMPLEMENTOS",
	"ICDPE-FIN-MANT-INSTALACIONES",
	"ICDPE-FIN-OBRAS",
	"ICDPE-FIN-ENTRENADORES",
	"ICDPE-FIN-ARBITROS",
	"ICDPE-FIN-VIATICOS",
	"ICDPE-FIN-SEGURIDAD",
)


@dataclass(frozen=True)
class FinanceItemSpec:
	item_code: str
	item_name: str
	item_group: str
	account_number: str  # income o expense según is_purchase
	cost_center_name: str
	is_sales: bool = True
	is_purchase: bool = False


INCOME_SPECS: tuple[FinanceItemSpec, ...] = (
	FinanceItemSpec(
		"ICDPE-FIN-ENTRADAS",
		"Entradas partidos / eventos",
		LEAF_ENTRADAS,
		"431003",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INDUMENTARIA",
		"Venta indumentaria",
		LEAF_SPONSORS,
		"451002",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-BUFFET",
		"Ventas buffet",
		LEAF_GASTRONOMIA,
		"441001",
		BUFFET_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-RESTAURANTE",
		"Ventas restaurante",
		LEAF_GASTRONOMIA,
		"441001",
		RESTAURANTE_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-CANON-CONCESION",
		"Canon concesión buffet/restaurante",
		LEAF_GASTRONOMIA,
		"441001",
		BUFFET_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SPONSOR",
		"Sponsoreo y publicidad",
		LEAF_SPONSORS,
		"451001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ALQUILER-TEMP",
		"Alquiler temporal instalaciones",
		LEAF_ALQUILERES,
		"421001",
		ALQUILER_TEMP_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SUBSIDIO",
		"Subsidios gubernamentales",
		LEAF_SUBSIDIOS,
		"491001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-DONACION",
		"Donaciones",
		LEAF_DONACIONES,
		"491001",
		ADMIN_CC,
	),
	FinanceItemSpec(
		"ICDPE-FIN-EVENTO-RECAUDACION",
		"Eventos de recaudación (rifas, cenas)",
		LEAF_RECAUDACION,
		"431003",
		ADMIN_CC,
	),
)

# Catálogo detallado de egresos (Secretaría / Flujo de Fondos).
EXPENSE_SPECS: tuple[FinanceItemSpec, ...] = (
	# 1. Impuestos y Tasas
	FinanceItemSpec(
		"ICDPE-FIN-IMP-ABL",
		"ABL y Tasas Inmobiliarias",
		GROUP_IMPUESTOS,
		"552001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-IMP-SELLOS",
		"Impuesto a los Sellos",
		GROUP_IMPUESTOS,
		"551001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-IMP-TASAS-MUNI",
		"Tasas e Inspecciones Municipales",
		GROUP_IMPUESTOS,
		"552001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-IMP-OBRA-CATASTRO",
		"Derechos de Obra y Tasas Catastrales",
		GROUP_IMPUESTOS,
		"552001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 2. Cargas Sociales y Obligaciones Laborales
	FinanceItemSpec(
		"ICDPE-FIN-CARGAS-931",
		"Formulario 931 ARCA",
		GROUP_CARGAS,
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-ART",
		"ART (Aseguradora de Riesgos del Trabajo)",
		GROUP_CARGAS,
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-UTEDYC",
		"Cuota Sindical UTEDYC y CCT",
		GROUP_CARGAS,
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SEGURO-VIDA",
		"Seguro de Vida Obligatorio",
		GROUP_CARGAS,
		"512001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 3. Remuneraciones Personal de Estructura
	FinanceItemSpec(
		"ICDPE-FIN-SUELDO-MANT",
		"Sueldo Personal Mantenimiento / Maestranza",
		GROUP_REMUNERACIONES,
		"511001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SUELDO-ADMIN",
		"Sueldo Personal Administrativo",
		GROUP_REMUNERACIONES,
		"511001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SUELDO-INTEND",
		"Sueldo Personal Intendencia",
		GROUP_REMUNERACIONES,
		"511001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 4. Honorarios y Servicios Deportivos
	FinanceItemSpec(
		"ICDPE-FIN-HON-ENTRENADOR",
		"Honorario Entrenador / Director Técnico",
		GROUP_HONORARIOS,
		"513001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-HON-PREP-FISICO",
		"Honorario Preparador Físico",
		GROUP_HONORARIOS,
		"513001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-HON-MONITOR",
		"Honorario Monitor / Ayudante de Campo",
		GROUP_HONORARIOS,
		"513001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-HON-ARBITROS",
		"Honorarios Árbitros",
		GROUP_HONORARIOS,
		"542001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-HON-MESA",
		"Honorarios Oficiales de Mesa",
		GROUP_HONORARIOS,
		"542001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 5. Afiliaciones y Aranceles Federativos
	FinanceItemSpec(
		"ICDPE-FIN-FED-INSCRIPCION",
		"Inscripción a Torneos y Ligas",
		GROUP_FEDERATIVOS,
		"543001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-FED-MULTAS",
		"Multas y Sanciones Federativas",
		GROUP_FEDERATIVOS,
		"543001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-FED-LICENCIAS",
		"Licencias y Pases de Jugadores",
		GROUP_FEDERATIVOS,
		"543001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 6. Insumos y Materiales Deportivos
	FinanceItemSpec(
		"ICDPE-FIN-INS-PELOTAS",
		"Material Deportivo - Pelotas",
		GROUP_INSUMOS,
		"541001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INS-REDES",
		"Material Deportivo - Redes y Accesorios",
		GROUP_INSUMOS,
		"541001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INS-INDUMENTARIA",
		"Indumentaria Deportiva y Competencia",
		GROUP_INSUMOS,
		"541001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 7. Reparaciones y Mantenimiento (Equipamiento)
	FinanceItemSpec(
		"ICDPE-FIN-MANT-TABLERO",
		'Mantenimiento de Tablero Electrónico y Reloj de 24"',
		GROUP_REPARACIONES,
		"531001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-MANT-PARQUET",
		"Reparación y Mantenimiento de Piso Deportivo (Parquet)",
		GROUP_REPARACIONES,
		"531001",
		BASQUET_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-MANT-CALDERAS",
		"Mantenimiento de Calderas y Bombas",
		GROUP_REPARACIONES,
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 8. Obras y Materiales de Infraestructura
	FinanceItemSpec(
		"ICDPE-FIN-OBRA-FERRETERIA",
		"Ferretería y Materiales de Construcción",
		GROUP_OBRAS,
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-OBRA-PINTURA",
		"Pintura General e Insumos",
		GROUP_OBRAS,
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-OBRA-ELECTRICOS",
		"Materiales Eléctricos y Luminarias LED",
		GROUP_OBRAS,
		"531001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 9. Servicios Públicos
	FinanceItemSpec(
		"ICDPE-FIN-LUZ",
		"Servicio de Energía Eléctrica (Luz)",
		GROUP_SERVICIOS_PUB,
		"521001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-GAS",
		"Servicio de Gas Natural",
		GROUP_SERVICIOS_PUB,
		"523001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-AGUA",
		"Servicio de Agua y Saneamiento",
		GROUP_SERVICIOS_PUB,
		"522001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-INTERNET",
		"Servicio de Internet y Telefonía",
		GROUP_SERVICIOS_PUB,
		"524001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	# 10. Seguros y Coberturas
	FinanceItemSpec(
		"ICDPE-FIN-SEGURO-RC",
		"Seguro de Responsabilidad Civil",
		GROUP_SEGUROS,
		"561001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-EMERGENCIAS-MED",
		"Servicio de Emergencias Médicas (Área Protegida)",
		GROUP_SEGUROS,
		"561001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
	FinanceItemSpec(
		"ICDPE-FIN-SEGURO-ACCIDENTES",
		"Seguro de Accidentes Personales (Deportistas)",
		GROUP_SEGUROS,
		"561001",
		ADMIN_CC,
		is_sales=False,
		is_purchase=True,
	),
)


def _ensure_uom(uom_name: str) -> None:
	if frappe.db.exists("UOM", uom_name):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)


def _ensure_item_group(name: str, *, parent: str, is_group: int = 0) -> None:
	"""Crea o alinea un Item Group (idempotente)."""
	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		changed = False
		if int(doc.is_group or 0) != int(is_group):
			doc.is_group = is_group
			changed = True
		if doc.parent_item_group != parent and parent:
			doc.parent_item_group = parent
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return

	if parent and not frappe.db.exists("Item Group", parent):
		frappe.throw(f"No existe el Item Group padre '{parent}'")

	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"parent_item_group": parent,
			"is_group": is_group,
		}
	).insert(ignore_permissions=True)


def ensure_egresos_item_group_tree() -> None:
	"""All Item Groups → 4 pilares → subgrupos hoja."""
	if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
		frappe.throw(f"No existe el Item Group raíz '{DEFAULT_ITEM_GROUP_ROOT}'")

	for central, leaves in EGRESO_TREE.items():
		_ensure_item_group(central, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=1)
		for leaf in leaves:
			_ensure_item_group(leaf, parent=central, is_group=0)

	# Árbol de ingresos (pilares nodos + hojas).
	ensure_ingresos_item_group_tree()


def _resolve_account(company: str, account_number: str) -> str | None:
	rows = frappe.get_all(
		"Account",
		filters={"company": company, "account_number": account_number, "is_group": 0},
		pluck="name",
		limit=1,
	)
	return rows[0] if rows else None


def _resolve_cost_center(cost_center_name: str) -> str | None:
	if frappe.db.exists("Cost Center", cost_center_name):
		return cost_center_name
	if frappe.db.exists("Cost Center", ADMIN_CC):
		return ADMIN_CC
	return None


def _upsert_item_defaults(
	item_name: str,
	company: str,
	*,
	income_account: str | None,
	expense_account: str | None,
	selling_cc: str | None,
	buying_cc: str | None,
) -> None:
	item = frappe.get_doc("Item", item_name)
	row = None
	for d in item.get("item_defaults") or []:
		if d.company == company:
			row = d
			break
	payload: dict = {"company": company}
	if income_account:
		payload["income_account"] = income_account
	if expense_account:
		payload["expense_account"] = expense_account
	if selling_cc:
		payload["selling_cost_center"] = selling_cc
	if buying_cc:
		payload["buying_cost_center"] = buying_cc

	if row is None:
		item.append("item_defaults", payload)
	else:
		for key, value in payload.items():
			if key != "company" and value:
				row.set(key, value)
	item.save(ignore_permissions=True)


def upsert_finance_item(spec: FinanceItemSpec) -> str:
	"""Crea o actualiza un Item financiero. Devuelve created|updated|skipped."""
	_ensure_uom("Servicio")
	if spec.item_group in EGRESO_LEAF_GROUPS or spec.item_group in INGRESO_LEAF_GROUPS or spec.item_group in (
		*INGRESO_PILLARS,
	):
		# Árboles de egreso/ingreso ya asegurados por el seed.
		if not frappe.db.exists("Item Group", spec.item_group):
			_ensure_item_group(spec.item_group, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=0)
	else:
		_ensure_item_group(spec.item_group, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=0)

	company = resolve_icdpe_company()
	account = _resolve_account(company, spec.account_number)
	cc = _resolve_cost_center(spec.cost_center_name)
	if not account or not cc:
		return "skipped"

	income = account if spec.is_sales else None
	expense = account if spec.is_purchase else None
	selling_cc = cc if spec.is_sales else None
	buying_cc = cc if spec.is_purchase else None

	if frappe.db.exists("Item", spec.item_code):
		item = frappe.get_doc("Item", spec.item_code)
		item.item_name = spec.item_name
		item.item_group = spec.item_group
		item.is_stock_item = 0
		item.stock_uom = "Servicio"
		item.is_sales_item = 1 if spec.is_sales else 0
		item.is_purchase_item = 1 if spec.is_purchase else 0
		item.disabled = 0
		item.save(ignore_permissions=True)
		_upsert_item_defaults(
			spec.item_code,
			company,
			income_account=income,
			expense_account=expense,
			selling_cc=selling_cc,
			buying_cc=buying_cc,
		)
		return "updated"

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": spec.item_code,
			"item_name": spec.item_name,
			"item_group": spec.item_group,
			"is_stock_item": 0,
			"is_sales_item": 1 if spec.is_sales else 0,
			"is_purchase_item": 1 if spec.is_purchase else 0,
			"stock_uom": "Servicio",
			"include_item_in_manufacturing": 0,
			"disabled": 0,
		}
	).insert(ignore_permissions=True)
	_upsert_item_defaults(
		spec.item_code,
		company,
		income_account=income,
		expense_account=expense,
		selling_cc=selling_cc,
		buying_cc=buying_cc,
	)
	return "created"


def disable_legacy_expense_items() -> int:
	"""Marca disabled=1 en ítems genéricos reemplazados. No borra."""
	n = 0
	for code in LEGACY_EXPENSE_ITEMS_TO_DISABLE:
		if not frappe.db.exists("Item", code):
			continue
		if int(frappe.db.get_value("Item", code, "disabled") or 0) == 1:
			continue
		frappe.db.set_value("Item", code, "disabled", 1, update_modified=False)
		n += 1
	return n


def run_finance_items_seed() -> dict[str, int]:
	"""Seed idempotente de jerarquía + ítems financieros."""
	ensure_egresos_item_group_tree()
	counts: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0, "disabled_legacy": 0, "error": 0}
	for spec in (*INCOME_SPECS, *EXPENSE_SPECS):
		result = upsert_finance_item(spec)
		counts[result] = counts.get(result, 0) + 1
	counts["disabled_legacy"] = disable_legacy_expense_items()
	from club_management.finance.setup.cleanup_residual_item_groups import (
		run_cleanup_residual_item_groups,
	)
	from club_management.finance.setup.fix_sponsors_y_ventas import run_fix_sponsors_y_ventas

	run_cleanup_residual_item_groups()
	run_fix_sponsors_y_ventas()
	return counts
