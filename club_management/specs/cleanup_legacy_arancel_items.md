# Spec: Apagar demo Shoe y eliminar aranceles `ICDPE-ARANCEL-MENSUAL-*` deshabilitados

Limpieza del catálogo de Items en sitios de desarrollo/migración: residuales de
fixtures ERPNext y aranceles paralelos viejos ya deshabilitados por `dedupe_items`
u operaciones previas.

**No toca:** egresos planos `LEGACY_EXPENSE_ITEMS_TO_DISABLE`, `ICDPE-SPONSOR-PUB`,
`ICDPE-VENTA-INDUMENTARIA`, cuotas `CLUB-*` / `Cuota Social *`.
Los códigos canónicos (`ICDPE-BOXEO-*`, etc.) no se eliminan.

También deshabilita `ICDPE-ARANCEL-MENSUAL-*` aún habilitados y remapea Links
al canónico (`arancel_catalogo_unico.md`).

---

## Scenario: deshabilita el ítem demo Shoe

Given existe el Item `138-CMS Shoe` (fixture ERPNext / CMS)
When corre `run_cleanup_legacy_arancel_items`
Then el Item queda `disabled = 1`
And no se elimina (puede tener Sales Invoice de prueba)

---

## Scenario: remapea grupos/planes al ítem canónico antes de borrar

Given un Item legacy en `LEGACY_ARANCEL_TO_CANONICAL` (p. ej. `ICDPE-ARANCEL-MENSUAL-BOXEO-1_VEZ` → `ICDPE-BOXEO-1-CLASE`)
And un `Grupo Actividad` (u otro Link) apunta al legacy
And el canónico existe
When corre `run_cleanup_legacy_arancel_items`
Then los Links pasan al canónico

---

## Scenario: elimina aranceles mensuales legacy ya deshabilitados

Given Items cuyo `name` empieza con `ICDPE-ARANCEL-MENSUAL-`
And están `disabled = 1`
And no están en `KEEP_ARANCEL_MENSUAL_CODES`
And no tienen líneas en Sales/Purchase Invoice
And no están referenciados por Link a Item en DocTypes de actividad/cargo (tras el remap)
When corre `run_cleanup_legacy_arancel_items`
Then se eliminan sus Item Price asociados
And se eliminan los Items

---

## Scenario: no elimina arancel mensual deshabilitado con factura

Given un Item `ICDPE-ARANCEL-MENSUAL-*` disabled con al menos una Sales Invoice Item
When corre la limpieza
Then el Item permanece (aparece en `skipped`)

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Lógica | `finance/setup/cleanup_legacy_arancel_items.py` |
| Patch | `patches/v1_0/cleanup_legacy_arancel_items.py` |
| Tests | `tests/test_cleanup_legacy_arancel_items.py` |
