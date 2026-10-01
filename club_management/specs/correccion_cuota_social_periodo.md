# Spec: Corrección de cuota social en facturas de un período (enmienda)

**Incidente 01/10/2026:** la deuda de `10/2026` se emitió con los montos de cuota social de ago/sep porque
`Club Settings.cuotas_categoria` no se había actualizado (sí `cuotas_vigente_desde = 2026-10-01`).

**Relacionado:** `valores_cuota_social_page.md`, `cuotas_sync_erpnext.md`, `cobranza_periodica_mensual.md`

---

## Valores vigentes desde 01/10/2026

| Categoría | Anterior (ago–sep 2026) | Vigente 01/10/2026 |
|-----------|------------------------:|-------------------:|
| Activo | 31.000 | 36.000 |
| Menor | 28.500 | 33.000 |
| 2° Hermano | 27.500 | 32.000 |
| 3° Hermano | 24.500 (Club Settings; código tenía 23.500) | 27.500 |
| Adherente | 19.500 | 22.000 |
| Jubilado | 5.500 | 6.000 |

- `CUOTAS_SOCIALES_VIGENTES` refleja la columna vigente.
- `CUOTAS_SOCIALES_ANTERIORES` conserva los montos previos: la clasificación de informes de cobranza
  (`bulk_payments._tarifas_cuota_social_catalogo`) debe reconocer **ambos** catálogos (meses históricos).

---

## Reglas de la corrección (`members/ops/corregir_cuota_social_periodo.run`)

- Universo: `Sales Invoice` con `periodo_cobro = <periodo>`, `docstatus = 1`, no devolución.
- Línea de cuota social: `item_code` ∈ ítems de `Club Settings.cuotas_categoria`, `item_cuota_social`,
  `ICDPE-CUOTA-SOCIAL` o legado `CLUB-Cuota-Social-Base`.
- Por línea, según la categoría del socio:
  - `rate == nuevo` → **ya correcta** (no se toca).
  - `rate == anterior` → **a corregir**.
  - otro valor / categoría sin monto → **revisar** (reporte, no se toca).
- Factura con pagos (`outstanding_amount < grand_total`) → **con pagos**: se respeta (adelantos), no se toca.
- Corrección = **enmienda**: cancelar la factura original y crear la copia `amended_from` con las líneas de
  cuota a corregir en el monto nuevo; el resto de líneas, socio, período, fechas (`set_posting_time = 1`) idénticos.
- Dry-run por defecto; apply protegido con `ensure_bulk_apply_allowed` (`local-dev` / `APPLY_PROD`).
- Idempotente: re-ejecutar no genera nuevas enmiendas.
- `commit=True` solo en ejecución por consola (commit por factura; rollback de la factura que falla).

---

## Scenario: valores vigentes y catálogo histórico

Given el código de la app
Then `CUOTAS_SOCIALES_VIGENTES` = Activo 36000, Menor 33000, 2° Hermano 32000, 3° Hermano 27500, Adherente 22000, Jubilado 6000
And el catálogo de tarifas de informes incluye 31000 y 36000.

## Scenario: dry-run detecta la factura a corregir sin modificarla

Given una factura impaga del período con cuota al monto anterior de la categoría
When corre `run(periodo, apply=False)`
Then el reporte la lista en `a_corregir` con monto anterior y nuevo
And la factura sigue submitted sin cambios.

## Scenario: apply protegido

When corre `run(periodo, apply=True)` sin token de confirmación
Then lanza `ValidationError` y no modifica facturas.

## Scenario: apply enmienda la factura

Given la factura del escenario anterior
When corre `run(periodo, apply=True, confirm="local-dev")`
Then la original queda cancelada
And existe una factura submitted con `amended_from` = original, mismo socio y período
And la línea de cuota tiene el monto nuevo y las demás líneas no cambian
And `grand_total` aumenta exactamente la diferencia.

When vuelve a correr el apply
Then no crea nuevas enmiendas (la factura figura como ya correcta).

## Scenario: factura con pagos se respeta

Given una factura del período con pagos parciales o totales
When corre `run`
Then figura en `con_pagos` y no se modifica.

## Scenario: monto inesperado va a revisar

Given una factura impaga con cuota a un monto que no es ni el anterior ni el nuevo de la categoría
When corre `run`
Then figura en `revisar` y no se modifica.
