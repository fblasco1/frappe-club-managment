"""Montos vigentes de cuota social por categoría de socio (ARS)."""

from __future__ import annotations

# Ítem ERPNext único para suscripción / facturación de cuota social.
CUOTA_SOCIAL_ITEM_CODE = "CLUB-Cuota-Social-Base"
CUOTA_SOCIAL_PLAN_NAME = "Plan Cuota Social Base"

# Montos operativos (planilla Mayo 2026 — solo cuotas sociales).
CUOTAS_SOCIALES_VIGENTES: tuple[tuple[str, float], ...] = (
	("Activo", 29_000.0),
	("Menor", 26_500.0),
	("2° Hermano", 25_500.0),
	("3° Hermano", 22_000.0),
	("Adherente", 17_500.0),
	("Jubilado", 5_500.0),
)
