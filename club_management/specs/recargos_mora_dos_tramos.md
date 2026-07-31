# Spec: Mora al cobro — tramos por vencimiento del período

Al cobrar, el recargo depende de la **fecha de pago** respecto de los
vencimientos del **período de la factura** (`periodo_cobro` = `MM/YYYY`):

| Momento de pago | Recargo | Base |
|-----------------|---------|------|
| Hasta el **1.er vencimiento** (día 10 del mes del período) inclusive | **0 %** | Saldo / valor facturado |
| Después del 1.er vencimiento y hasta el **2.º vencimiento** (último día del mes del período) inclusive | **+10 %** | Valor vigente del concepto |
| **Después** del 2.º vencimiento | **+15 %** (= 10 % + 5 %) | **Cuota / valor del mes en que se paga** |

```
si pago ≤ 1.er venc. del período     → sin mora
si 1.er < pago ≤ 2.º venc. del período → valor × (1 + 0,10)
si pago > 2.º venc. del período        → valor_mes_pago × (1 + 0,15)
```

**No** se multiplica ningún % por la cantidad de meses de atraso.

**Relacionado:** `flujo_cobranzas.md`, `cobranza_config_club_settings.md`,
`cobranza_recargo_segundo_vencimiento.md` (job legado), `registrar_cobro_fecha.md`,
`cobro_multi_factura_medios_mixtos.md`

---

## Ejemplo canónico (período marzo)

- 1.er vencimiento = **10/03**; 2.º = **31/03**.
- Cuota marzo = 10; cuota abril = **12**.

| Fecha de pago | Tramo | Monto |
|---------------|-------|-------|
| 08/03 | ninguno | outstanding / valor período (sin %) |
| 15/03 | post 1.er | `10 × 1,10` = **11,00** (o valor vigente marzo) |
| 08/04 | post 2.º | `12 × 1,15` = **13,80** |
| 15/07 | post 2.º | valor julio × **1,15** |

---

## Decisiones (cerradas)

| ID | Decisión |
|----|----------|
| **D1** | El 10 % aplica si `posting_date` es **posterior** al 1.er vencimiento del **período adeudado** (día `dia_primer_vencimiento` de ese mes). |
| **D2** | El 5 % extra aplica solo si `posting_date` es **posterior** al 2.º vencimiento del período (default: último día de ese mes). Junto con el 10 % suma **15 %**. |
| **D3** | Post 2.º vencimiento: base = **valor vigente del mes de pago** (revalorización). |
| **D4** | El job legado `recargo_segundo_vencimiento_pct` **no** es la fuente de verdad; la mora se calcula **al cobrar**. |

---

## Configuración (`Club Settings`) — simplificada

| Campo | Label sugerido | Default | Rol |
|-------|----------------|---------|-----|
| `dia_primer_vencimiento` | Día primer vencimiento | 10 | 1.er vencimiento del mes del período |
| `dia_segundo_vencimiento` | Segundo vencimiento | Último día del mes | 2.º vencimiento del período |
| `recargo_post_vencimiento_pct` | Recargo post 1.er vencimiento (%) | 10 | +10 % entre 1.er y 2.º venc. |
| `recargo_mes_vencido_pct` | Recargo extra post 2.º vencimiento (%) | 5 | +5 % adicional tras el 2.º (total 15 %) |
| `item_recargo_mora` | Ítem recargo mora | — | Obligatorio para crear SI de ajuste |
| `recargo_segundo_vencimiento_pct` | Recargo 2.º vencimiento (%) — legado | 10 | Solo job histórico; no usar en mora al cobro |

---

## Scenario: mismo mes, antes del día 10

Given deuda período `03/2026`
When paga el 2026-03-08
Then tramo = ninguno
And monto = outstanding del grupo (sin recargo).

---

## Scenario: mismo mes, entre día 10 y fin de mes (+10 %)

Given deuda período `03/2026`, valor vigente = 12
And `recargo_post_vencimiento_pct = 10`
When paga el 2026-03-15
Then tramo = post_primer
And monto = `12 * 1.10` = 13,20.

---

## Scenario: mes siguiente (+15 % sobre cuota del mes de pago)

Given deuda período `03/2026`
And valor cuota vigente en abril = 12
And `recargo_post_vencimiento_pct = 10`, `recargo_mes_vencido_pct = 5`
When paga el 2026-04-08 (posterior al 31/03)
Then tramo = post_segundo
And monto = `12 * 1.15` = 13,80
And la composición muestra `12.000 × (1 + 10% + 5%)` (o equivalente 15 %), **sin** `×N meses`.

---

## Scenario: varios meses después sigue siendo +15 % fijo

Given deuda de marzo, paga en julio con valor julio = 29000
When calcula mora
Then monto = `29000 * 1.15` = 33350
And **no** escala el % con la cantidad de meses.

---

## Scenario: preview Desk y cobro

Given facturas seleccionadas
When Secretaría abre Registrar cobro / llama `preview_mora_al_cobro`
Then ve total y composición por tramo
And al confirmar se crea SI de ajuste si hace falta (`item_recargo_mora` obligatorio)
And la suma de medios coincide con el total a cobrar.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Servicio | `members/services/mora_al_cobro.py` |
| Settings UI | `members/doctype/club_settings/club_settings.json` |
| Tests | `members/tests/test_mora_valor_actual.py` |
