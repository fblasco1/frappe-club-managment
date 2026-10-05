"""Montos vigentes de cuota social por categoría de socio (ARS)."""

from __future__ import annotations

# Ítem ERPNext único para suscripción / facturación de cuota social.
CUOTA_SOCIAL_ITEM_CODE = "ICDPE-CUOTA-SOCIAL"
CUOTA_SOCIAL_PLAN_NAME = "Plan Cuota Social Base"
# Ítem anterior a la consolidación; sigue presente en facturas emitidas (p. ej. 09/2026).
CUOTA_SOCIAL_LEGACY_ITEM_CODE = "CLUB-Cuota-Social-Base"

# Montos operativos vigentes desde 01/10/2026.
CUOTAS_SOCIALES_VIGENTES: tuple[tuple[str, float], ...] = (
	("Activo", 36_000.0),
	("Menor", 33_000.0),
	("2° Hermano", 32_000.0),
	("3° Hermano", 27_500.0),
	("Adherente", 22_000.0),
	("Jubilado", 6_000.0),
)

# Montos ago–sep 2026 (Club Settings en prod). Necesarios para clasificar informes de meses
# históricos y para corregir facturas emitidas con valores viejos.
CUOTAS_SOCIALES_ANTERIORES: tuple[tuple[str, float], ...] = (
	("Activo", 31_000.0),
	("Menor", 28_500.0),
	("2° Hermano", 27_500.0),
	("3° Hermano", 24_500.0),
	("Adherente", 19_500.0),
	("Jubilado", 5_500.0),
)

# 3° Hermano figuraba en código con 23.500 antes de alinearse a Club Settings.
_TARIFAS_HISTORICAS_EXTRA: tuple[float, ...] = (23_500.0,)

TARIFAS_CUOTA_SOCIAL_CATALOGO: tuple[float, ...] = tuple(
	dict.fromkeys(
		[m for _c, m in CUOTAS_SOCIALES_VIGENTES]
		+ [m for _c, m in CUOTAS_SOCIALES_ANTERIORES]
		+ list(_TARIFAS_HISTORICAS_EXTRA)
	)
)
