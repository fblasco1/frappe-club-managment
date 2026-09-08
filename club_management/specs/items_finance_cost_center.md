# Spec: Ítems financieros y Cost Center automático

Ingresos eventuales/comerciales y egresos operativos se facturan con **Items** que traen cuenta + Cost Center por defecto (`Item Default`), alineados al plan ICDPE.

**Relacionado:** `carga_rapida_ingreso_egreso.md`, `basquet_cost_center_consolidado.md`

---

## Scenario: seed crea ítems de ingreso comercial

Given Company ICDPE y cuentas/CC importados
When se ejecuta el seed de ítems financieros
Then existen ítems para entradas, indumentaria, buffet, restaurante, sponsoreo, alquiler temporal, donaciones (códigos `ICDPE-FIN-*`)
And cada uno tiene `Item Default` con `income_account` y `selling_cost_center`.

---

## Scenario: seed crea ítems de egreso

Given el mismo setup
When corre el seed
Then existen ítems de gasto del catálogo detallado (remuneraciones, 931/cargas, servicios públicos, federativos, etc.)
And `Item Default` incluye `expense_account` y `buying_cost_center`.

Ver jerarquía completa en `catalogo_egresos_item_groups.md`.

---

## Scenario: resolver defaults desde Item

Given un Item de ingreso con defaults
When la carga rápida omite Cost Center explícito
Then se usa `selling_cost_center` del Item Default de la Company.

---

## Scenario: resolver defaults de egreso

Given un Item de gasto con defaults
When la carga rápida omite Cost Center
Then se usa `buying_cost_center` del Item Default.

---

## Scenario: facturar sin CC resoluble falla

Given un Item sin defaults de CC y sin CC en el request
When se intenta registrar
Then ValidationError.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Catálogo | `finance/setup/icdpe_finance_items.py` |
| Seed masters | `finance/setup/seed_finance_masters.py` |
| Resolución CC | `finance/services/carga_rapida.py` |
| Patch | `patches/v1_0/seed_finance_masters.py` |
| Tests | `tests/test_items_finance_cost_center.py` |
