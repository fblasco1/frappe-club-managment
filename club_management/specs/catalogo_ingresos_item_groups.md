# Spec: Catálogo de ingresos — 4 pilares Item Group

Refactoriza los grupos fragmentados `ICDPE / *` de ingresos a **4 pilares**
bajo `All Item Groups`. Los Items se reasignan; los grupos viejos se eliminan
si quedan vacíos (o se archivan bajo un nodo legacy si hay vínculos).

**Relacionado:** `catalogo_egresos_item_groups.md`, `items_finance_cost_center.md`,
`cargo_extra_conceptos_y_facturacion.md`

---

## Jerarquía

```
All Item Groups
 ├── Ingresos de Socios y Membresías
 ├── Ingresos por Actividades Deportivas
 ├── Ingresos Comerciales y Alquileres
 └── Ingresos Institucionales
```

Los 4 pilares son hoja (`is_group = 0`) y reciben los Items directamente.

---

## Mapeo de migración

| Origen | Destino |
|--------|---------|
| `ICDPE / Cuotas y membresías`, `ICDPE / Cargos varios` | Ingresos de Socios y Membresías |
| `ICDPE / Aranceles deportes`, `… fitness`, `… actividades`, `ICDPE / Federaciones deportes`, `ICDPE / Actividades puntuales` | Ingresos por Actividades Deportivas |
| `ICDPE / Alquileres`, `ICDPE / Comercial`, `ICDPE / Gastronomía POS` | Ingresos Comerciales y Alquileres |
| `ICDPE-FIN-ENTRADAS`, `…-ALQUILER-TEMP`, `…-BUFFET`, `…-RESTAURANTE`, `…-CANON-CONCESION`, `…-SPONSOR`, `…-INDUMENTARIA` | Ingresos Comerciales y Alquileres |
| `ICDPE-FIN-SUBSIDIO`, `…-DONACION`, `…-EVENTO-RECAUDACION` | Ingresos Institucionales |

---

## Scenario: seed crea 4 pilares de ingreso

Given `All Item Groups`
When corre el seed/migración de ingresos
Then existen los 4 pilares con padre `All Item Groups` y `is_group = 0`

---

## Scenario: ítems se reasignan a pilares

Given ítems en grupos `ICDPE / *` de ingreso
When corre la migración
Then cada ítem mapeado tiene el `item_group` del pilar correspondiente
And los ítems `ICDPE-FIN-*` de Tesorería quedan en Comercial o Institucional según la tabla

---

## Scenario: limpieza de grupos viejos

Given grupos `ICDPE /` de ingreso sin ítems tras el move
When corre el cleanup
Then se intenta `delete_doc` del Item Group
And si falla por vínculos, el grupo se mueve bajo `ICDPE / Legacy ingresos`

---

## Scenario: idempotente

Given migración ya aplicada
When se vuelve a ejecutar
Then no hay error y el estado permanece correcto

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Catálogo + migración | `finance/setup/icdpe_income_item_groups.py` |
| Patch | `patches/v1_0/migrate_ingresos_item_groups.py` |
| Tests | `tests/test_catalogo_ingresos_item_groups.py` |
