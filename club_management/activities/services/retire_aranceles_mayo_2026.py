"""Retiro de ítems, planes y vínculos del seed de aranceles Mayo 2026."""

from __future__ import annotations

import frappe

MAYO_ITEM_PREFIX = "ICDPE-ARANCEL-MAYO26"

# Grupos creados por el seed Mayo 2026 (nombre completo `Actividad / Título`).
_MAYO_GRUPO_NAMES: tuple[str, ...] = (
	"Basquet Masculino / U9 / U11 / U13 — Azul y Amarillo",
	"Basquet Masculino / U15 / U17 / U21 — Tira Azul",
	"Basquet Masculino / U15 / U17 / U21 — Tira Amarillo",
	"Basquet Masculino / Escuelita",
	"Basquet Masculino / Flex",
	"Basquet Femenino / Escuelita y Femenino",
	"Futbol / Futbol",
	"Futbol / Escuelita",
	"Voley Femenino / Voley",
	"Voley Femenino / Escuelita",
	"Iniciacion Deportiva / 1 vez por semana",
	"Iniciacion Deportiva / 2 veces por semana",
	"Gimnasia Artistica / 1 vez por semana",
	"Gimnasia Artistica / 2 veces por semana",
	"Patin Artistico / Inicial",
	"Patin Artistico / Intermedio 1",
	"Patin Artistico / Avanzado 3",
	"Patin Artistico / Danza Patin",
	"Patin Artistico / Adulto",
	"Funcional / GAP",
	"Funcional / CrossFit",
	"Funcional / Pase 3 clases",
	"Funcional / Pase 4 clases",
	"Yoga / 1 clase por semana",
	"Yoga / 2 clases por semana",
	"Gimnasio Fitness / General",
	"Gimnasio Fitness / Socios",
	"Boxeo / 1 vez por semana",
	"Boxeo / 2 veces por semana",
	"Boxeo / 3 veces por semana",
)

# Actividades planas del seed cuyo ítem era Mayo 2026.
_MAYO_ACTIVIDADES_PLANAS: tuple[str, ...] = (
	"Danza",
	"Taekwondo",
	"Shui Lu",
	"Ritmos Latinos",
)


def _mayo_item_codes() -> list[str]:
	return frappe.get_all(
		"Item",
		filters={"item_code": ["like", f"{MAYO_ITEM_PREFIX}%"]},
		pluck="name",
	)


def _cancel_subscriptions_for_items(item_codes: list[str]) -> int:
	if not item_codes or not frappe.db.exists("DocType", "Subscription Plan"):
		return 0

	plans = frappe.get_all(
		"Subscription Plan",
		filters={"item": ["in", item_codes]},
		pluck="name",
	)
	if not plans:
		return 0

	cancelled = 0
	for sub_name in frappe.get_all(
		"Subscription",
		filters={"status": ["in", ["Active", "Trialing", "Grace Period"]]},
		pluck="name",
	):
		sub = frappe.get_doc("Subscription", sub_name)
		plan_names = {row.plan for row in (sub.plans or [])}
		if not plan_names.intersection(plans):
			continue
		sub.flags.ignore_permissions = True
		if sub.status != "Cancelled":
			sub.cancel_subscription()
			cancelled += 1
	return cancelled


def retire_aranceles_mayo_2026() -> dict[str, int]:
	"""Elimina artefactos ERPNext del seed Mayo 2026 (aranceles de actividades)."""
	item_codes = _mayo_item_codes()
	counts = {
		"items": len(item_codes),
		"subscriptions_cancelled": 0,
		"plans_deleted": 0,
		"prices_deleted": 0,
		"links_cleared": 0,
		"grupos_disabled": 0,
	}

	if item_codes:
		counts["subscriptions_cancelled"] = _cancel_subscriptions_for_items(item_codes)

		for plan_name in frappe.get_all(
			"Subscription Plan",
			filters={"item": ["in", item_codes]},
			pluck="name",
		):
			frappe.delete_doc("Subscription Plan", plan_name, force=1, ignore_permissions=True)
			counts["plans_deleted"] += 1

		for price_name in frappe.get_all(
			"Item Price",
			filters={"item_code": ["in", item_codes]},
			pluck="name",
		):
			frappe.delete_doc("Item Price", price_name, force=1, ignore_permissions=True)
			counts["prices_deleted"] += 1

		for doctype in ("Grupo Actividad", "Actividad"):
			for name in frappe.get_all(doctype, filters={"item": ["in", item_codes]}, pluck="name"):
				frappe.db.set_value(doctype, name, "item", None, update_modified=True)
				counts["links_cleared"] += 1

		for item_code in item_codes:
			if frappe.db.exists("Item", item_code):
				frappe.delete_doc("Item", item_code, force=1, ignore_permissions=True)

	for grupo_name in _MAYO_GRUPO_NAMES:
		if not frappe.db.exists("Grupo Actividad", grupo_name):
			continue
		frappe.db.set_value("Grupo Actividad", grupo_name, "item", None, update_modified=False)
		frappe.db.set_value("Grupo Actividad", grupo_name, "habilitada", 0, update_modified=True)
		counts["grupos_disabled"] += 1

	for actividad in _MAYO_ACTIVIDADES_PLANAS:
		if frappe.db.exists("Actividad", actividad):
			frappe.db.set_value("Actividad", actividad, "item", None, update_modified=True)
			counts["links_cleared"] += 1

	return counts
