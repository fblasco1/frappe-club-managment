"""
Bootstrap de **cuota social** y suscripciones mensuales (ERPNext Subscriptions).

Ejecución desde bench:

  bench --site <sitio> execute club_management.setup.suscripciones_cobro_mensual.run

Requisitos:
- ERPNext instalado (DocTypes Item, Item Price, Subscription Plan, Subscription).
- Una Company con cuenta de ingreso y centro de costos configurables (o defaults ERPNext).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from club_management.finance.setup.icdpe_income_item_groups import LEAF_CUOTAS

# ---------------------------------------------------------------------------
# Constantes operativas del club
# ---------------------------------------------------------------------------

ITEM_GROUP_ROOT = "All Item Groups"
ITEM_GROUP_NAME = LEAF_CUOTAS
PRICE_LIST_NAME = "Standard Selling"
STOCK_UOM = "Nos"

# Estados de suscripción considerados "vigentes" para evitar duplicados.
_ACTIVE_SUBSCRIPTION_STATUSES = ("Active", "Trialing", "Grace Period")


@dataclass(frozen=True)
class ClubFeeItemSpec:
	"""Definición del ítem de cuota social."""

	item_code: str
	item_name: str
	initial_rate: float
	plan_name: str


CLUB_CUOTA_SOCIAL_ITEM = ClubFeeItemSpec(
	item_code="CLUB-Cuota-Social-Base",
	item_name="Cuota Social Base",
	initial_rate=29_000.0,
	plan_name="Plan Cuota Social Base",
)

# Ítem único de cuota social para suscripciones ERPNext.
CLUB_FEE_ITEMS: tuple[ClubFeeItemSpec, ...] = (CLUB_CUOTA_SOCIAL_ITEM,)


def erpnext_subscriptions_disponible() -> bool:
	"""True si el sitio tiene los DocTypes de suscripción ERPNext."""
	required = ("Subscription Plan", "Subscription", "Item Price")
	return all(frappe.db.exists("DocType", doctype) for doctype in required)


def _resolve_company() -> str:
	"""Company del club (Club Settings) o default ERPNext."""
	if frappe.db.exists("DocType", "Club Settings"):
		company = frappe.db.get_single_value("Club Settings", "company")
		if company:
			return company

	from erpnext import get_default_company

	company = get_default_company()
	if not company:
		frappe.throw(_("No hay Company configurada en el sitio."))
	return company


def _resolve_income_account(company: str) -> str:
	"""Cuenta de ingreso por defecto de la compañía o primera cuenta Income leaf."""
	account = frappe.get_cached_value("Company", company, "default_income_account")
	if account:
		return account

	rows = frappe.get_all(
		"Account",
		filters={"company": company, "root_type": "Income", "is_group": 0},
		pluck="name",
		limit=1,
	)
	if rows:
		return rows[0]

	frappe.throw(
		_("No se encontró cuenta de ingreso para {0}. Configure default_income_account en Company.").format(
			company
		)
	)


def _resolve_cost_center(company: str) -> str:
	"""Centro de costos por defecto ERPNext para la compañía."""
	from erpnext import get_default_cost_center

	cost_center = get_default_cost_center(company)
	if cost_center:
		return cost_center

	rows = frappe.get_all(
		"Cost Center",
		filters={"company": company, "is_group": 0},
		pluck="name",
		limit=1,
	)
	if rows:
		return rows[0]

	frappe.throw(_("No se encontró centro de costos para {0}.").format(company))


def _ensure_uom(uom_name: str = STOCK_UOM) -> None:
	if frappe.db.exists("UOM", uom_name):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)


def ensure_item_group_cuotas_y_aranceles() -> str:
	"""Asegura la hoja canónica «Cuotas sociales» del árbol de ingresos."""
	from club_management.finance.setup.icdpe_income_item_groups import (
		ensure_ingresos_item_group_tree,
	)

	ensure_ingresos_item_group_tree()
	if frappe.db.exists("Item Group", ITEM_GROUP_NAME):
		return ITEM_GROUP_NAME
	frappe.throw(_("No existe el Item Group '{0}' tras asegurar el árbol de ingresos.").format(ITEM_GROUP_NAME))


def _upsert_item_default(item_name: str, company: str, income_account: str, cost_center: str) -> None:
	"""Mantiene la fila de `item_defaults` por compañía (cuenta + CC)."""
	item = frappe.get_doc("Item", item_name)
	row = next((d for d in (item.get("item_defaults") or []) if d.company == company), None)
	if row is None:
		item.append(
			"item_defaults",
			{
				"company": company,
				"income_account": income_account,
				"selling_cost_center": cost_center,
			},
		)
	else:
		row.income_account = income_account
		row.selling_cost_center = cost_center
	item.save(ignore_permissions=True)


def ensure_service_item(
	spec: ClubFeeItemSpec,
	*,
	company: str,
	income_account: str,
	cost_center: str,
	item_group: str,
) -> str:
	"""
	Crea o actualiza un Item de servicio (sin stock) con defaults contables.

	`is_stock_item` queda en 0 — requisito crítico para cuotas/aranceles.
	"""
	_ensure_uom()
	payload = {
		"item_name": spec.item_name,
		"item_group": item_group,
		"disabled": 0,
		"is_stock_item": 0,
		"is_sales_item": 1,
		"stock_uom": STOCK_UOM,
		"include_item_in_manufacturing": 0,
	}

	if frappe.db.exists("Item", spec.item_code):
		item = frappe.get_doc("Item", spec.item_code)
		changed = False
		for field, value in payload.items():
			if getattr(item, field, None) != value:
				setattr(item, field, value)
				changed = True
		if changed:
			item.save(ignore_permissions=True)
	else:
		item = frappe.get_doc({"doctype": "Item", "item_code": spec.item_code, **payload})
		item.insert(ignore_permissions=True)

	_upsert_item_default(spec.item_code, company, income_account, cost_center)
	return spec.item_code


def ensure_item_price(
	*,
	item_code: str,
	price_list: str,
	rate: float,
	currency: str,
) -> str:
	"""Crea o actualiza Item Price en la lista indicada (p. ej. Standard Selling)."""
	if not frappe.db.exists("Price List", price_list):
		frappe.throw(_("No existe la Price List '{0}'.").format(price_list))

	existing = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list},
		"name",
	)
	if existing:
		frappe.db.set_value("Item Price", existing, "price_list_rate", flt(rate), update_modified=True)
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"price_list_rate": flt(rate),
			"currency": currency,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_subscription_plan(
	spec: ClubFeeItemSpec,
	*,
	item_code: str,
	company: str,
	currency: str,
	cost_center: str,
) -> str:
	"""
	Crea o actualiza Subscription Plan mensual (Month / count 1).

	El precio se toma de la Price List «Standard Selling» (`Based On Price List`).
	"""
	payload = {
		"item": item_code,
		"currency": currency,
		"billing_interval": "Month",
		"billing_interval_count": 1,
		"price_determination": "Based On Price List",
		"price_list": PRICE_LIST_NAME,
		"cost_center": cost_center,
	}

	if frappe.db.exists("Subscription Plan", spec.plan_name):
		plan = frappe.get_doc("Subscription Plan", spec.plan_name)
		for field, value in payload.items():
			setattr(plan, field, value)
		plan.save(ignore_permissions=True)
		return plan.name

	plan = frappe.get_doc({"doctype": "Subscription Plan", "plan_name": spec.plan_name, **payload})
	plan.insert(ignore_permissions=True)
	return plan.name


def ensure_subscription_plan_for_item(
	item_code: str,
	*,
	rate: float | None = None,
) -> str | None:
	"""
	Obtiene o crea un Subscription Plan mensual para un ítem arbitrario.

	Usado al validar socios (cuota social) y al inscribir actividades (arancel).
	"""
	if not erpnext_subscriptions_disponible():
		return None
	if not item_code or not frappe.db.exists("Item", item_code):
		return None

	existing = frappe.db.get_value("Subscription Plan", {"item": item_code}, "name")
	if existing:
		return existing

	company = _resolve_company()
	currency = frappe.get_cached_value("Company", company, "default_currency") or "ARS"
	cost_center = _resolve_cost_center(company)

	resolved_rate = flt(rate)
	if resolved_rate <= 0:
		resolved_rate = flt(frappe.db.get_value("Item", item_code, "standard_rate"))
	if resolved_rate <= 0:
		resolved_rate = flt(
			frappe.db.get_value(
				"Item Price",
				{"item_code": item_code, "price_list": PRICE_LIST_NAME},
				"price_list_rate",
			)
		)

	plan_name = f"Plan — {item_code}"
	payload = {
		"plan_name": plan_name,
		"item": item_code,
		"currency": currency,
		"billing_interval": "Month",
		"billing_interval_count": 1,
		"price_determination": "Fixed Rate",
		"cost": resolved_rate,
		"cost_center": cost_center,
	}

	if frappe.db.exists("Subscription Plan", plan_name):
		plan = frappe.get_doc("Subscription Plan", plan_name)
		for field, value in payload.items():
			if field != "plan_name":
				setattr(plan, field, value)
		plan.save(ignore_permissions=True)
		return plan.name

	plan = frappe.get_doc({"doctype": "Subscription Plan", **payload})
	plan.insert(ignore_permissions=True)
	return plan.name


def setup_club_fee_items_and_plans() -> dict[str, Any]:
	"""
	Pipeline completo: Item Group → Items → Item Prices → Subscription Plans.

	Devuelve un resumen con nombres creados/actualizados.
	"""
	if not erpnext_subscriptions_disponible():
		frappe.throw(_("ERPNext Subscriptions no está disponible en este sitio."))

	company = _resolve_company()
	currency = frappe.get_cached_value("Company", company, "default_currency") or "ARS"
	income_account = _resolve_income_account(company)
	cost_center = _resolve_cost_center(company)
	item_group = ensure_item_group_cuotas_y_aranceles()

	items: list[str] = []
	plans: list[str] = []
	prices: list[str] = []

	for spec in CLUB_FEE_ITEMS:
		item_code = ensure_service_item(
			spec,
			company=company,
			income_account=income_account,
			cost_center=cost_center,
			item_group=item_group,
		)
		items.append(item_code)

		price_name = ensure_item_price(
			item_code=item_code,
			price_list=PRICE_LIST_NAME,
			rate=spec.initial_rate,
			currency=currency,
		)
		prices.append(price_name)

		plan_name = ensure_subscription_plan(
			spec,
			item_code=item_code,
			company=company,
			currency=currency,
			cost_center=cost_center,
		)
		plans.append(plan_name)

	return {
		"company": company,
		"item_group": item_group,
		"items": items,
		"item_prices": prices,
		"subscription_plans": plans,
	}


def setup_cuota_social_item_and_plan(*, reference_rate: float | None = None) -> dict[str, str]:
	"""Bootstrap mínimo: un ítem + plan de cuota social."""
	if not erpnext_subscriptions_disponible():
		return {"item": CLUB_CUOTA_SOCIAL_ITEM.item_code, "plan": CLUB_CUOTA_SOCIAL_ITEM.plan_name}

	company = _resolve_company()
	currency = frappe.get_cached_value("Company", company, "default_currency") or "ARS"
	income_account = _resolve_income_account(company)
	cost_center = _resolve_cost_center(company)
	item_group = ensure_item_group_cuotas_y_aranceles()
	spec = CLUB_CUOTA_SOCIAL_ITEM
	rate = flt(reference_rate) if reference_rate is not None else spec.initial_rate
	if rate <= 0:
		rate = spec.initial_rate

	item_code = ensure_service_item(
		spec,
		company=company,
		income_account=income_account,
		cost_center=cost_center,
		item_group=item_group,
	)
	frappe.db.set_value("Item", item_code, "standard_rate", rate, update_modified=True)
	ensure_item_price(
		item_code=item_code,
		price_list=PRICE_LIST_NAME,
		rate=rate,
		currency=currency,
	)
	plan_name = ensure_subscription_plan(
		spec,
		item_code=item_code,
		company=company,
		currency=currency,
		cost_center=cost_center,
	)
	if frappe.db.get_value("Subscription Plan", plan_name, "price_determination") == "Fixed Rate":
		frappe.db.set_value("Subscription Plan", plan_name, "cost", rate, update_modified=True)
	return {"item": item_code, "plan": plan_name}


def _find_active_subscription_for_plan(customer_name: str, plan_name: str) -> str | None:
	"""Busca suscripción vigente del cliente que ya incluya el plan."""
	if not frappe.db.exists("Customer", customer_name):
		return None

	active_subs = frappe.get_all(
		"Subscription",
		filters={
			"party_type": "Customer",
			"party": customer_name,
			"status": ["in", list(_ACTIVE_SUBSCRIPTION_STATUSES)],
		},
		pluck="name",
	)
	for sub_name in active_subs:
		if frappe.db.exists(
			"Subscription Plan Detail",
			{"parent": sub_name, "parenttype": "Subscription", "plan": plan_name},
		):
			return sub_name
	return None


def _get_active_subscriptions(customer_name: str) -> list[str]:
	if not customer_name:
		return []
	return frappe.get_all(
		"Subscription",
		filters={
			"party_type": "Customer",
			"party": customer_name,
			"status": ["in", list(_ACTIVE_SUBSCRIPTION_STATUSES)],
		},
		pluck="name",
		order_by="creation asc",
	)


def _get_primary_active_subscription(customer_name: str) -> str | None:
	subs = _get_active_subscriptions(customer_name)
	return subs[0] if subs else None


def _subscription_has_plan(sub_name: str, plan_name: str) -> bool:
	return bool(
		frappe.db.exists(
			"Subscription Plan Detail",
			{"parent": sub_name, "parenttype": "Subscription", "plan": plan_name},
		)
	)


def _create_member_subscription(
	customer_name: str,
	plan_name: str,
	*,
	start_date: str | None = None,
) -> frappe.model.document.Document:
	company = _resolve_company()
	cost_center = _resolve_cost_center(company)
	sub_start = getdate(start_date or nowdate())
	subscription = frappe.get_doc(
		{
			"doctype": "Subscription",
			"party_type": "Customer",
			"party": customer_name,
			"company": company,
			"cost_center": cost_center,
			"start_date": sub_start,
			"submit_invoice": 0,
			"generate_invoice_at": "Beginning of the current subscription period",
			"generate_new_invoices_past_due_date": 0,
			"plans": [{"plan": plan_name, "qty": 1}],
		}
	)
	subscription.insert(ignore_permissions=True)
	return subscription


def consolidate_customer_subscriptions(customer_name: str) -> str | None:
	"""Unifica planes de varias suscripciones activas en la primera (migración legacy)."""
	subs = _get_active_subscriptions(customer_name)
	if not subs:
		return None
	primary = subs[0]
	if len(subs) == 1:
		return primary

	primary_doc = frappe.get_doc("Subscription", primary)
	for sub_name in subs[1:]:
		other = frappe.get_doc("Subscription", sub_name)
		for row in other.plans or []:
			if row.plan and not _subscription_has_plan(primary, row.plan):
				primary_doc.append("plans", {"plan": row.plan, "qty": row.qty or 1})
		other.flags.ignore_permissions = True
		if other.status != "Cancelled":
			other.cancel_subscription()
	primary_doc.flags.ignore_permissions = True
	primary_doc.save(ignore_permissions=True)
	return primary


def add_plan_to_member_subscription(
	customer_name: str,
	plan_name: str,
	*,
	start_date: str | None = None,
) -> dict[str, Any]:
	"""Agrega un plan a la suscripción activa del cliente (una suscripción unificada)."""
	if not erpnext_subscriptions_disponible():
		frappe.throw(_("ERPNext Subscriptions no está disponible en este sitio."))
	if not customer_name or not frappe.db.exists("Customer", customer_name):
		frappe.throw(_("Cliente inválido: {0}").format(customer_name or "—"))
	if not plan_name or not frappe.db.exists("Subscription Plan", plan_name):
		frappe.throw(_("Plan de suscripción inválido: {0}").format(plan_name or "—"))

	consolidate_customer_subscriptions(customer_name)
	existing = _find_active_subscription_for_plan(customer_name, plan_name)
	if existing:
		return {
			"subscription": existing,
			"created": False,
			"status": frappe.db.get_value("Subscription", existing, "status"),
		}

	sub_name = _get_primary_active_subscription(customer_name)
	if sub_name:
		subscription = frappe.get_doc("Subscription", sub_name)
		subscription.append("plans", {"plan": plan_name, "qty": 1})
		subscription.flags.ignore_permissions = True
		subscription.save(ignore_permissions=True)
		return {
			"subscription": subscription.name,
			"created": False,
			"plan_added": True,
			"status": subscription.status,
		}

	subscription = _create_member_subscription(customer_name, plan_name, start_date=start_date)
	return {
		"subscription": subscription.name,
		"created": True,
		"status": subscription.status,
	}


def remove_plan_from_member_subscription(customer_name: str, plan_name: str) -> dict[str, Any] | None:
	"""Quita un plan de la suscripción activa; cancela la suscripción si queda vacía."""
	if not erpnext_subscriptions_disponible() or not customer_name or not plan_name:
		return None

	sub_name = _find_active_subscription_for_plan(customer_name, plan_name)
	if not sub_name:
		return None

	subscription = frappe.get_doc("Subscription", sub_name)
	subscription.plans = [row for row in (subscription.plans or []) if row.plan != plan_name]
	subscription.flags.ignore_permissions = True
	if not subscription.plans:
		if subscription.status != "Cancelled":
			subscription.cancel_subscription()
		return {
			"subscription": sub_name,
			"cancelled": True,
			"status": frappe.db.get_value("Subscription", sub_name, "status"),
		}
	subscription.save(ignore_permissions=True)
	return {
		"subscription": sub_name,
		"plan_removed": True,
		"status": subscription.status,
	}


def enroll_member_to_subscription(
	customer_name: str,
	plan_name: str,
	*,
	start_date: str | None = None,
) -> dict[str, Any]:
	"""
	Alta (wrapper) de un socio/cliente en un plan de suscripción mensual.

	- `customer_name`: ID del `Customer` ERPNext (socio facturable).
	- `plan_name`: ID del `Subscription Plan` (campo `plan_name`).

	Crea o amplía la suscripción activa del cliente con el plan indicado.
	La factura mensual la emite el job del club (`submit_invoice = 0`).
	"""
	return add_plan_to_member_subscription(customer_name, plan_name, start_date=start_date)


def cancel_member_subscription_for_plan(customer_name: str, plan_name: str) -> dict[str, Any] | None:
	"""Quita el plan de la suscripción activa del cliente (idempotente)."""
	return remove_plan_from_member_subscription(customer_name, plan_name)


def cancel_all_member_subscriptions(customer_name: str) -> list[dict[str, Any]]:
	"""Cancela todas las suscripciones vigentes de un `Customer`."""
	if not erpnext_subscriptions_disponible() or not customer_name:
		return []

	cancelled: list[dict[str, Any]] = []
	active_subs = frappe.get_all(
		"Subscription",
		filters={
			"party_type": "Customer",
			"party": customer_name,
			"status": ["in", list(_ACTIVE_SUBSCRIPTION_STATUSES)],
		},
		pluck="name",
	)
	for sub_name in active_subs:
		subscription = frappe.get_doc("Subscription", sub_name)
		subscription.flags.ignore_permissions = True
		if subscription.status != "Cancelled":
			subscription.cancel_subscription()
		cancelled.append(
			{
				"subscription": sub_name,
				"cancelled": True,
				"status": frappe.db.get_value("Subscription", sub_name, "status"),
			}
		)
	return cancelled


def run() -> dict[str, Any]:
	"""Entry point para `bench execute` — solo cuota social."""
	return setup_cuota_social_item_and_plan()
