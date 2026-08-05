# Spec: Catálogo de egresos — Item Groups e Items (Secretaría / Tesorería)

Normaliza la carga de egresos de Secretaría y el reporte de Flujo de Fondos con
**4 pilares** bajo `All Item Groups` y subgrupos hoja. Los Items son de compra
no stock (`is_stock_item = 0`).

**Relacionado:** `items_finance_cost_center.md`, `flujo_egresos_borrador_aprobacion.md`,
`proyeccion_flujo_fondos.md`, `recordatorio_provision_sueldos_secretaria.md`

---

## Jerarquía

```
All Item Groups
 ├── Gastos de Estructura y Servicios
 │    ├── Servicios Públicos
 │    ├── Impuestos y Tasas
 │    └── Seguros y Coberturas
 ├── Gastos de Personal (Nómina)
 │    ├── Remuneraciones y Sueldos
 │    └── Cargas Sociales y Contribuciones Patronales
 ├── Costos Operativos Deportivos
 │    ├── Honorarios y Servicios Profesionales
 │    ├── Afiliaciones y Aranceles Federativos
 │    └── Insumos y Materiales Deportivos
 └── Mantenimiento e Infraestructura
      ├── Reparaciones y Repuestos
      └── Obras y Materiales
```

Los pilares tienen `is_group = 1`. Los subgrupos hoja (`is_group = 0`) reciben los Items.
Los nombres de Item Group **no** incluyen emojis (Desk / búsqueda / NestedSet).

---

## Scenario: seed crea 4 pilares bajo All Item Groups

Given Company ICDPE y el Item Group raíz `All Item Groups`
When se ejecuta el seed de catálogo de egresos
Then existen los 4 pilares con `parent_item_group = All Item Groups` y `is_group = 1`
And cada subgrupo hoja tiene como padre su pilar correspondiente y `is_group = 0`

---

## Scenario: seed crea ítems de egreso no stock

Given el seed de egresos
When corre
Then existen los ítems del catálogo (códigos `ICDPE-FIN-*` detallados)
And cada uno tiene `is_stock_item = 0`, `is_purchase_item = 1`, `stock_uom = Servicio`
And cada uno pertenece a su Item Group hoja correspondiente
And `Item Default` incluye `expense_account` y `buying_cost_center` cuando hay cuenta/CC

---

## Scenario: ítems genéricos previos se deshabilitan

Given ítems legacy fuera del catálogo vigente
  (p. ej. `ICDPE-FIN-SUELDOS`, `ICDPE-FIN-VIATICOS`, `ICDPE-FIN-SEGURIDAD`, …)
When corre el seed
Then esos códigos quedan `disabled = 1`
And no se borran (integridad referencial de Purchase Invoice históricas)
And se reasignan a hojas del árbol de egresos (no quedan en `ICDPE / Finanzas egresos`)

---

## Scenario: seed es idempotente

Given el catálogo ya sembrado
When se vuelve a ejecutar el seed
Then no hay error de llave duplicada
And los grupos e ítems se actualizan in-place (nombre, grupo, flags)

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Catálogo + seed | `finance/setup/icdpe_finance_items.py` |
| Orquestación | `finance/setup/seed_finance_masters.py` |
| Patch | `patches/v1_0/seed_egresos_catalogo_secretaria.py` |
| Tests | `tests/test_catalogo_egresos_item_groups.py` |
