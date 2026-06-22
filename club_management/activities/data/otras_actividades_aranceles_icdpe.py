"""Ítems y tarifas de otras actividades ICDPE (gimnasia, boxeo, yoga, fitness, etc.)."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import ArancelItemSpec

ITEM_GIMNASIA_1_CLASE = "ICDPE-GIMNASIA-ARTISTICA-1-CLASE"
ITEM_GIMNASIA_2_CLASES = "ICDPE-GIMNASIA-ARTISTICA-2-CLASES"
ITEM_DANZA = "ICDPE-DANZA"
ITEM_BOXEO_1_CLASE = "ICDPE-BOXEO-1-CLASE"
ITEM_BOXEO_2_CLASES = "ICDPE-BOXEO-2-CLASES"
ITEM_BOXEO_3_CLASES = "ICDPE-BOXEO-3-CLASES"
ITEM_YOGA_1_CLASE = "ICDPE-YOGA-1-CLASE"
ITEM_YOGA_2_CLASES = "ICDPE-YOGA-2-CLASES"
ITEM_GYM_NO_SOCIO = "ICDPE-GYM-PASE-LIBRE-NO-SOCIO"
ITEM_GYM_SOCIO = "ICDPE-GYM-PASE-LIBRE-SOCIO"
ITEM_INICIACION_1_CLASE = "ICDPE-INICIACION-DEPORTIVA-1-CLASE"
ITEM_INICIACION_2_CLASES = "ICDPE-INICIACION-DEPORTIVA-2-CLASES"
ITEM_TAEKWONDO = "ICDPE-TAEKWONDO"
ITEM_SHUI_LU = "ICDPE-SHUI-LU"
ITEM_RITMOS_LATINOS = "ICDPE-RITMOS-LATINOS"

CC_GIMNASIA = "Deportes - Gimnasia Artistica - ICDPE"
CC_BOXEO = "Deportes - Boxeo - ICDPE"
CC_TAEKWONDO = "Deportes - Taekwondo - ICDPE"
CC_SHUI_LU = "Deportes - Shui Lu - ICDPE"
CC_DANZA = "Actividades - Danza - ICDPE"
CC_YOGA = "Actividades - Yoga - ICDPE"
CC_RITMOS = "Actividades - Ritmos Latinos - ICDPE"
CC_INICIACION = "Actividades - Iniciacion Deportiva - ICDPE"
CC_FITNESS = "Fitness - Gimnasio de Musculacion - ICDPE"

OTRAS_ACTIVIDADES_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_GIMNASIA_1_CLASE,
		"Arancel mensual gimnasia artística — 1 clase por semana",
		15500.0,
		CC_GIMNASIA,
	),
	ArancelItemSpec(
		ITEM_GIMNASIA_2_CLASES,
		"Arancel mensual gimnasia artística — 2 clases por semana",
		20500.0,
		CC_GIMNASIA,
	),
	ArancelItemSpec(ITEM_DANZA, "Arancel mensual danza", 15500.0, CC_DANZA),
	ArancelItemSpec(ITEM_BOXEO_1_CLASE, "Arancel mensual boxeo — 1 clase por semana", 14500.0, CC_BOXEO),
	ArancelItemSpec(ITEM_BOXEO_2_CLASES, "Arancel mensual boxeo — 2 clases por semana", 26000.0, CC_BOXEO),
	ArancelItemSpec(ITEM_BOXEO_3_CLASES, "Arancel mensual boxeo — 3 clases por semana", 38000.0, CC_BOXEO),
	ArancelItemSpec(ITEM_YOGA_1_CLASE, "Arancel mensual yoga — 1 clase por semana", 23500.0, CC_YOGA),
	ArancelItemSpec(ITEM_YOGA_2_CLASES, "Arancel mensual yoga — 2 clases por semana", 28500.0, CC_YOGA),
	ArancelItemSpec(
		ITEM_GYM_NO_SOCIO,
		"Arancel mensual gimnasio — pase libre no socio",
		44000.0,
		CC_FITNESS,
	),
	ArancelItemSpec(
		ITEM_GYM_SOCIO,
		"Arancel mensual gimnasio — pase libre socio",
		22000.0,
		CC_FITNESS,
	),
	ArancelItemSpec(
		ITEM_INICIACION_1_CLASE,
		"Arancel mensual iniciación deportiva — 1 clase por semana",
		15500.0,
		CC_INICIACION,
	),
	ArancelItemSpec(
		ITEM_INICIACION_2_CLASES,
		"Arancel mensual iniciación deportiva — 2 clases por semana",
		20500.0,
		CC_INICIACION,
	),
	ArancelItemSpec(ITEM_TAEKWONDO, "Arancel mensual taekwondo", 21500.0, CC_TAEKWONDO),
	ArancelItemSpec(ITEM_SHUI_LU, "Arancel mensual shui lu", 37000.0, CC_SHUI_LU),
	ArancelItemSpec(ITEM_RITMOS_LATINOS, "Arancel mensual ritmos latinos", 21500.0, CC_RITMOS),
)
