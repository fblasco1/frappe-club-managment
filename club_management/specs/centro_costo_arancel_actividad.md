# Spec: Centro de costo del arancel de actividad

Los ingresos por **arancel de actividad** deben imputarse al **centro de costo de la actividad**
(p. ej. `Basquet - ICDPE`), no al centro de costo por defecto de la empresa
(`Administración - ICDPE`). Esto vale tanto para la **línea de la factura** (`Sales Invoice Item`)
como para el **asiento contable** (`GL Entry`) del ingreso.

La **cuota social** imputa a un centro de costo **propio** («Cuotas Sociales»), para separar
en el estado de resultados el ingreso social del gasto de estructura (`Administración`).

**Relacionado:** `cobranza_periodica_mensual.md`, `tesoreria_panel_operaciones.md`

## Contexto

- Cada ítem de arancel deportivo define su centro de costo propio en `Item Default.selling_cost_center`
  (ver `activities/services/deporte_icdpe_items.py`).
- La factura mensual se genera en `members/services/cobranza_periodica.py` a partir de
  `build_invoice_items_for_socio` (`cobranza_manual.py`).

---

## Scenario: la factura mensual imputa el arancel al centro de costo de la actividad

Given un ítem de arancel con `Item Default.selling_cost_center = "Basquet - ICDPE"`
And un socio activo inscripto en esa actividad
When se genera la factura mensual (cuota + arancel)
Then la línea del arancel tiene `cost_center = "Basquet - ICDPE"`
And el `GL Entry` del ingreso del arancel tiene `cost_center = "Basquet - ICDPE"`
And la línea de la cuota social imputa al centro de costo «Cuotas Sociales».

---

## Scenario: la cuota social imputa a su centro de costo propio

Given el centro de costo «Cuotas Sociales» configurado en el `Item Default` de la cuota social
And un socio activo
When se genera la factura mensual de la cuota
Then la línea de la cuota tiene `cost_center = "Cuotas Sociales - <abbr>"`
And el `GL Entry` del ingreso de la cuota tiene ese mismo centro de costo.

---

## Scenario: re-etiquetado de facturas históricas (backfill)

Given facturas de venta ya emitidas (`docstatus = 1`) cuyas líneas de arancel quedaron con
`cost_center = "Administración - ICDPE"`
When se ejecuta el patch de re-asignación
Then cada línea de arancel toma el centro de costo de su actividad (según `Item Default`)
And se reponen los `GL Entry` del ingreso con el centro de costo correcto
And las facturas con varias actividades de distinto centro de costo quedan correctamente separadas.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Resolución de CC por ítem | `members/services/cobranza_manual.py` (`resolve_cost_center_item`) |
| CC Cuotas Sociales | `finance/setup/cuota_social_cost_center.py` (`ensure_cuota_social_cost_center`) |
| Backfill | `members/services/cost_center_backfill.py` (`reasignar_cost_center_aranceles`) |
| Patches | `patches/v1_0/reasignar_cost_center_aranceles.py`, `patches/v1_0/add_cuota_social_cost_center.py` |
| Tests | `members/tests/test_cost_center_arancel.py`, `members/tests/test_cuota_social_cost_center.py` |
