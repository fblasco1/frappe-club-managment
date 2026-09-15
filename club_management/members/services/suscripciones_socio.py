"""Suscripciones ERPNext unificadas: cuota social + aranceles por inscripción."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_item_arancel_inscripcion,
	resolve_monto_arancel_inscripcion,
)
from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	resolve_cuota_social,
)
from club_management.setup.suscripciones_cobro_mensual import (
	cancel_all_member_subscriptions,
	consolidate_customer_subscriptions,
	enroll_member_to_subscription,
	ensure_subscription_plan_for_item,
	erpnext_subscriptions_disponible,
	remove_plan_from_member_subscription,
)


def suscripciones_habilitadas() -> bool:
	return erpnext_cobranza_disponible() and erpnext_subscriptions_disponible()


def _customer_for_socio(socio_name: str) -> str | None:
	for field in ("socio", "custom_socio"):
		if frappe.get_meta("Customer").has_field(field):
			customer = frappe.db.get_value("Customer", {field: socio_name}, "name")
			if customer:
				return customer
	return None


def _plan_for_item(item_code: str, *, rate: float | None = None) -> str | None:
	if not item_code:
		return None
	return ensure_subscription_plan_for_item(item_code, rate=rate)


def expected_plan_names_for_socio(socio_name: str) -> set[str]:
	"""Planes de suscripción que deberían estar activos para el socio."""
	plans: set[str] = set()
	monto, item_cuota = resolve_cuota_social(socio_name)
	if item_cuota and flt(monto) > 0:
		plan = _plan_for_item(item_cuota, rate=monto)
		if plan:
			plans.add(plan)

	for ins in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa"},
		pluck="name",
	):
		item_code, monto = resolve_monto_arancel_inscripcion(ins)
		if not item_code or flt(monto) <= 0:
			continue
		plan = _plan_for_item(item_code, rate=monto)
		if plan:
			plans.add(plan)
	return plans


def sync_suscripciones_socio(socio_name: str) -> dict[str, Any]:
	"""Sincroniza planes de cuota + aranceles activos en una suscripción unificada."""
	if not suscripciones_habilitadas():
		return {"skipped": True, "reason": "subscriptions_unavailable"}

	expected = expected_plan_names_for_socio(socio_name)
	if not expected:
		cancelled = cancel_all_suscripciones_socio(socio_name)
		return {"socio": socio_name, "expected_plans": [], "cancelled": len(cancelled)}

	customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
	consolidate_customer_subscriptions(customer)

	added: list[str] = []
	for plan_name in sorted(expected):
		result = enroll_member_to_subscription(customer, plan_name)
		if result.get("created") or result.get("plan_added"):
			added.append(plan_name)

	# Quitar planes de aranceles que ya no aplican (cuota se mantiene vía expected).
	current_plans = _active_plan_names_for_customer(customer)
	for plan_name in current_plans - expected:
		remove_plan_from_member_subscription(customer, plan_name)

	sub_name = frappe.db.get_value(
		"Subscription",
		{
			"party_type": "Customer",
			"party": customer,
			"status": ["in", ["Active", "Trialing", "Grace Period"]],
		},
		"name",
	)
	return {
		"socio": socio_name,
		"customer": customer,
		"subscription": sub_name,
		"expected_plans": sorted(expected),
		"plans_added": added,
	}


def _active_plan_names_for_customer(customer_name: str) -> set[str]:
	from club_management.setup.suscripciones_cobro_mensual import _get_active_subscriptions

	plans: set[str] = set()
	for sub_name in _get_active_subscriptions(customer_name):
		for row in frappe.get_all(
			"Subscription Plan Detail",
			filters={"parent": sub_name, "parenttype": "Subscription"},
			pluck="plan",
		):
			if row:
				plans.add(row)
	return plans


def enroll_socio_cuota_social(socio_name: str) -> dict[str, Any] | None:
	if not suscripciones_habilitadas():
		return None
	return sync_suscripciones_socio(socio_name)


def enroll_socio_arancel_inscripcion(inscripcion_name: str) -> dict[str, Any] | None:
	if not suscripciones_habilitadas():
		return None
	socio_name = frappe.db.get_value(INSCRIPCION_DOCTYPE, inscripcion_name, "socio")
	if not socio_name:
		return None
	estado = frappe.db.get_value(INSCRIPCION_DOCTYPE, inscripcion_name, "estado")
	if estado != "Activa":
		return None
	return sync_suscripciones_socio(socio_name)


def cancel_arancel_inscripcion(inscripcion_name: str) -> dict[str, Any] | None:
	if not suscripciones_habilitadas():
		return None
	socio_name = frappe.db.get_value(INSCRIPCION_DOCTYPE, inscripcion_name, "socio")
	if not socio_name:
		return None
	return sync_suscripciones_socio(socio_name)


def cancel_all_suscripciones_socio(socio_name: str) -> list[dict[str, Any]]:
	if not suscripciones_habilitadas():
		return []
	customer = _customer_for_socio(socio_name)
	if customer:
		return cancel_all_member_subscriptions(customer)
	return []


def sync_suscripcion_cuota_al_validar_socio(socio_name: str) -> None:
	try:
		sync_suscripciones_socio(socio_name)
	except Exception:
		frappe.log_error(
			title=f"Suscripción socio — {socio_name}",
			message=frappe.get_traceback(),
		)


def sync_suscripciones_al_dar_baja_socio(socio_name: str) -> None:
	try:
		cancel_all_suscripciones_socio(socio_name)
	except Exception:
		frappe.log_error(
			title=f"Cancelar suscripciones socio — {socio_name}",
			message=frappe.get_traceback(),
		)


def sync_suscripciones_al_dar_alta_socio(socio_name: str) -> None:
	try:
		sync_suscripciones_socio(socio_name)
	except Exception:
		frappe.log_error(
			title=f"Restaurar suscripciones socio — {socio_name}",
			message=frappe.get_traceback(),
		)


def sync_suscripcion_tras_inscripcion(doc: frappe.model.document.Document, method: str | None = None) -> None:
	"""Hook DocType `Inscripcion Actividad`."""
	if doc.get("estado") == "Activa":
		enroll_socio_arancel_inscripcion(doc.name)
	else:
		cancel_arancel_inscripcion(doc.name)
