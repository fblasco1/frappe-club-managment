"""Ítems y tarifas de otras actividades ICDPE (gimnasia, boxeo, yoga, fitness, etc.)."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import (
	ArancelItemSpec,
	format_arancel_mensual_item_name,
)

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
ITEM_FUNCIONAL_1_CLASE = "ICDPE-FUNCIONAL-1-CLASE"
ITEM_FUNCIONAL_2_CLASES = "ICDPE-FUNCIONAL-2-CLASES"
ITEM_TAEKWONDO = "ICDPE-TAEKWONDO"
ITEM_SHUI_LU = "ICDPE-SHUI-LU"
ITEM_RITMOS_LATINOS = "ICDPE-RITMOS-LATINOS"

CC_GIMNASIA = "Gimnasia Artistica - ICDPE"
CC_BOXEO = "Boxeo - ICDPE"
CC_TAEKWONDO = "Taekwondo - ICDPE"
CC_SHUI_LU = "Shui Lu - ICDPE"
CC_DANZA = "Danza - ICDPE"
CC_YOGA = "Yoga - ICDPE"
CC_RITMOS = "Ritmos Latinos - ICDPE"
CC_INICIACION = "Iniciacion Deportiva - ICDPE"
CC_FITNESS = "Gimnasio de Musculacion - ICDPE"
CC_FUNCIONAL = "Funcional - ICDPE"

OTRAS_ACTIVIDADES_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_GIMNASIA_1_CLASE,
		format_arancel_mensual_item_name("GIMNASIA ARTISTICA", "1 CLASE POR SEMANA"),
		15500.0,
		CC_GIMNASIA,
	),
	ArancelItemSpec(
		ITEM_GIMNASIA_2_CLASES,
		format_arancel_mensual_item_name("GIMNASIA ARTISTICA", "2 CLASES POR SEMANA"),
		20500.0,
		CC_GIMNASIA,
	),
	ArancelItemSpec(ITEM_DANZA, format_arancel_mensual_item_name("DANZA"), 15500.0, CC_DANZA),
	ArancelItemSpec(
		ITEM_BOXEO_1_CLASE,
		format_arancel_mensual_item_name("BOXEO", "1 CLASE POR SEMANA"),
		14500.0,
		CC_BOXEO,
	),
	ArancelItemSpec(
		ITEM_BOXEO_2_CLASES,
		format_arancel_mensual_item_name("BOXEO", "2 CLASES POR SEMANA"),
		26000.0,
		CC_BOXEO,
	),
	ArancelItemSpec(
		ITEM_BOXEO_3_CLASES,
		format_arancel_mensual_item_name("BOXEO", "3 CLASES POR SEMANA"),
		38000.0,
		CC_BOXEO,
	),
	ArancelItemSpec(
		ITEM_YOGA_1_CLASE,
		format_arancel_mensual_item_name("YOGA", "1 CLASE POR SEMANA"),
		23500.0,
		CC_YOGA,
	),
	ArancelItemSpec(
		ITEM_YOGA_2_CLASES,
		format_arancel_mensual_item_name("YOGA", "2 CLASES POR SEMANA"),
		28500.0,
		CC_YOGA,
	),
	ArancelItemSpec(
		ITEM_GYM_NO_SOCIO,
		format_arancel_mensual_item_name("GIMNASIO FITNESS", "NO SOCIO"),
		44000.0,
		CC_FITNESS,
	),
	ArancelItemSpec(
		ITEM_GYM_SOCIO,
		format_arancel_mensual_item_name("GIMNASIO FITNESS", "SOCIO"),
		22000.0,
		CC_FITNESS,
	),
	ArancelItemSpec(
		ITEM_INICIACION_1_CLASE,
		format_arancel_mensual_item_name("INICIACION DEPORTIVA", "1 CLASE POR SEMANA"),
		15500.0,
		CC_INICIACION,
	),
	ArancelItemSpec(
		ITEM_INICIACION_2_CLASES,
		format_arancel_mensual_item_name("INICIACION DEPORTIVA", "2 CLASES POR SEMANA"),
		20500.0,
		CC_INICIACION,
	),
	ArancelItemSpec(
		ITEM_FUNCIONAL_1_CLASE,
		format_arancel_mensual_item_name("FUNCIONAL", "1 VEZ POR SEMANA"),
		18000.0,
		CC_FUNCIONAL,
	),
	ArancelItemSpec(
		ITEM_FUNCIONAL_2_CLASES,
		format_arancel_mensual_item_name("FUNCIONAL", "2 VECES POR SEMANA"),
		27500.0,
		CC_FUNCIONAL,
	),
	ArancelItemSpec(
		ITEM_TAEKWONDO, format_arancel_mensual_item_name("TAEKWONDO"), 21500.0, CC_TAEKWONDO
	),
	ArancelItemSpec(ITEM_SHUI_LU, format_arancel_mensual_item_name("SHUI LU"), 37000.0, CC_SHUI_LU),
	ArancelItemSpec(
		ITEM_RITMOS_LATINOS,
		format_arancel_mensual_item_name("RITMOS LATINOS"),
		21500.0,
		CC_RITMOS,
	),
)
