"""Montos vigentes de cuota social por categoría de socio (ARS)."""

from __future__ import annotations

# Ítem ERPNext único para suscripción / facturación de cuota social.
CUOTA_SOCIAL_ITEM_CODE = "ICDPE-CUOTA-SOCIAL"
CUOTA_SOCIAL_PLAN_NAME = "Plan Cuota Social Base"

# Montos operativos vigentes (ago 2026).
CUOTAS_SOCIALES_VIGENTES: tuple[tuple[str, float], ...] = (
	("Activo", 31_000.0),
	("Menor", 28_500.0),
	("2° Hermano", 27_500.0),
	("3° Hermano", 23_500.0),
	("Adherente", 19_500.0),
	("Jubilado", 5_500.0),
)
