# Spec: Catálogo único de aranceles mensuales

Un solo etiquetado visible y un solo `item_code` operativo por concepto.

**Formato de nombre:** `ARANCEL MENSUAL - …` (`arancel_item_naming.md`).

**Códigos canónicos:** prefijos `ICDPE-BASQUET-*`, `ICDPE-BOXEO-*`, `ICDPE-VOLEY-*`,
`ICDPE-FUTBOL-*`, `ICDPE-PATIN-*`, `ICDPE-YOGA-*`, `ICDPE-GIMNASIA-*`,
`ICDPE-GYM-*`, `ICDPE-FUNCIONAL-*`, `ICDPE-DANZA`, `ICDPE-TAEKWONDO`,
`ICDPE-SHUI-LU`, `ICDPE-RITMOS-LATINOS`, `ICDPE-INICIACION-DEPORTIVA-*`.

**Legacy a retirar:** todo `ICDPE-ARANCEL-MENSUAL-*` (nombres «Arancel Mensual …»,
placeholders de actividad, etc.).

**Relacionado:** `cleanup_legacy_arancel_items.md`, `basquet_aranceles_icdpe.md`,
`patin_otras_actividades_aranceles_icdpe.md`.

---

## Scenario: Boxeo — solo 1/2/3 clases canónicos

Given coexistían `ICDPE-BOXEO-*-CLASE(S)` y `ICDPE-ARANCEL-MENSUAL-BOXEO-*`
When corre `retire_enabled_legacy_arancel_mensual`
Then quedan habilitados solo `ICDPE-BOXEO-1-CLASE`, `…-2-CLASES`, `…-3-CLASES`
And con `item_name` = `ARANCEL MENSUAL - BOXEO/N CLASE(S) POR SEMANA`
And los `ICDPE-ARANCEL-MENSUAL-BOXEO*` quedan disabled (y se borran si no hay SI).

---

## Scenario: Actividad apunta a canónico

Given `Actividad` Futbol / Voley Femenino / Funcional tenían `item` legacy
When corre el patch de retiro + sync catálogo
Then `Actividad.item` apunta al canónico (`ICDPE-FUTBOL-TABI-A`, `ICDPE-VOLEY-FEDERADO`, `ICDPE-FUNCIONAL-1-CLASE`, …).

---

## Scenario: legacy con facturas no se borra

Given `ICDPE-ARANCEL-MENSUAL-PATIN-AVANZADO_3` disabled con Sales Invoice Items
When corre la limpieza
Then el Item permanece disabled (no se elimina).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Mapa + retiro | `finance/setup/cleanup_legacy_arancel_items.py` |
| Catálogo actividad | `activities/services/actividades_icdpe_catalog.py` |
| Patch | `patches/v1_0/retire_legacy_arancel_mensual_catalog.py` |
| Tests | `tests/test_cleanup_legacy_arancel_items.py` |
