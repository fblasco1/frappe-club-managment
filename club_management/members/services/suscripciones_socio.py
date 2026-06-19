"""Integración de suscripciones ERPNext — solo cuota social del socio."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	resolve_cuota_social,
)
from club_management.setup.suscripciones_cobro_mensual import (
	cancel_all_member_subscriptions,
	enroll_member_to_subscription,
	ensure_subscription_plan_for_item,
	erpnext_subscriptions_disponible,
)


def suscripciones_habilitadas() -> bool:
	"""True si el sitio puede crear Customer + Subscription."""
	return erpnext_cobranza_disponible() and erpnext_subscriptions_disponible()


def enroll_socio_cuota_social(socio_name: str) -> dict[str, Any] | None:
	"""
	Alta de suscripción mensual de cuota social según categoría del socio.

	Usa el ítem configurado en `Club Settings.cuotas_categoria` (típicamente
	`CLUB-Cuota-Social-Base`) y el monto de la categoría del socio.
	"""
	if not suscripciones_habilitadas():
		return None

	monto, item_code = resolve_cuota_social(socio_name)
	if not item_code or flt(monto) <= 0:
		return None

	customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
	plan_name = ensure_subscription_plan_for_item(item_code, rate=monto)
	if not plan_name:
		return None

	return enroll_member_to_subscription(customer, plan_name)


def cancel_all_suscripciones_socio(socio_name: str) -> list[dict[str, Any]]:
	"""Cancela la(s) suscripción(es) de cuota social del socio."""
	if not suscripciones_habilitadas():
		return []

	for field in ("socio", "custom_socio"):
		if not frappe.get_meta("Customer").has_field(field):
			continue
		customer = frappe.db.get_value("Customer", {field: socio_name}, "name")
		if customer:
			return cancel_all_member_subscriptions(customer)
	return []


def sync_suscripcion_cuota_al_validar_socio(socio_name: str) -> None:
	"""Hook post-validación: cuota social sin bloquear el flujo principal."""
	try:
		enroll_socio_cuota_social(socio_name)
	except Exception:
		frappe.log_error(
			title=f"Suscripción cuota social — {socio_name}",
			message=frappe.get_traceback(),
		)


def sync_suscripciones_al_dar_baja_socio(socio_name: str) -> None:
	"""Hook baja de socio: cancela suscripciones de cuota social."""
	try:
		cancel_all_suscripciones_socio(socio_name)
	except Exception:
		frappe.log_error(
			title=f"Cancelar suscripciones socio — {socio_name}",
			message=frappe.get_traceback(),
		)
