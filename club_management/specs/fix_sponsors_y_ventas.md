# Spec: Corregir Sponsors y ventas (egresos mal ubicados)

La hoja `Sponsors y ventas` solo debe contener **ingresos** comerciales de
sponsoreo e indumentaria. Los ítems de egreso `ICDPE-FIN-*` del catálogo
detallado no deben vivir ahí.

**Relacionado:** `catalogo_ingresos_item_groups.md`, `catalogo_egresos_item_groups.md`,
`cleanup_residual_item_groups.md`

---

## Decisión de catálogo (sponsors)

| Código | Estado |
|--------|--------|
| `ICDPE-FIN-SPONSOR` | **Canónico** — sponsoreo / publicidad |
| `ICDPE-SPONSOR-PUB` | **Disabled** — duplicado; no usar en cobros nuevos |
| `ICDPE-FIN-INDUMENTARIA` | Activo — venta indumentaria |
| `ICDPE-VENTA-INDUMENTARIA` | Disabled (legacy) |

---

## Scenario: egresos salen de Sponsors

Given ítems de `EXPENSE_SPECS` (luz, sueldos, honorarios, …) con
`item_group = Sponsors y ventas`
When corre la corrección
Then cada uno queda en la hoja de egreso de su `FinanceItemSpec`
And `Sponsors y ventas` solo retiene los códigos de ingreso de sponsors/indumentaria

---

## Scenario: resolve de ingreso no empuja egresos a Sponsors

Given un código de egreso `ICDPE-FIN-LUZ` (u otro de `EXPENSE_SPECS`)
When se llama `resolve_ingreso_leaf_for_item`
Then **no** se resuelve a `Sponsors y ventas` por el solo prefijo `ICDPE-FIN-`
And la reasignación de ingresos **omite** ítems de compra / `EXPENSE_SPECS`

---

## Scenario: sponsor canónico

Given `ICDPE-SPONSOR-PUB` habilitado
When corre la corrección
Then queda `disabled = 1`
And `ICDPE-FIN-SPONSOR` permanece habilitado en `Sponsors y ventas`

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Corrección | `finance/setup/fix_sponsors_y_ventas.py` |
| Patch | `patches/v1_0/fix_sponsors_y_ventas.py` |
| Tests | `tests/test_fix_sponsors_y_ventas.py` |
