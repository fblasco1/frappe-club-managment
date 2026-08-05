# Spec: Catálogo de ingresos — jerarquía unificada (espejo egresos)

Los **4 pilares de ingreso** pasan a nodos (`is_group = 1`) con subgrupos hoja
que reciben Items — misma forma que egresos (`catalogo_egresos_item_groups.md`).
Bajo Actividades Deportivas hay un nivel intermedio (Deportes / Fitness).

**Relacionado:** `catalogo_egresos_item_groups.md`, `items_finance_cost_center.md`,
`cargo_extra_conceptos_y_facturacion.md`, `cuotas_sociales_suscripcion.md`

**Decisión:** un solo ítem `ICDPE-CUOTA-SOCIAL` + Item Prices por categoría;
el subgrupo «Cuotas sociales» organiza el árbol (no se parten N ítems por categoría).

---

## Jerarquía

```
All Item Groups
├── Ingresos de Socios y Membresías          (is_group=1)
│   ├── Cuotas sociales                      (hoja)
│   └── Cargos extras y mora                 (hoja)
├── Ingresos por Actividades Deportivas      (is_group=1)
│   ├── Deportes                             (is_group=1)
│   │   ├── Básquet / Fútbol / Vóley / Patín / Boxeo / …
│   ├── Fitness y actividades                (is_group=1)
│   │   ├── Gimnasio / Funcional y CrossFit / Yoga / Danza / …
│   ├── Cuotas federativas                   (hoja)
│   └── Actividades puntuales                (hoja)
├── Ingresos Comerciales y Alquileres        (is_group=1)
│   ├── Alquileres / Gastronomía / Sponsors y ventas / Entradas y eventos
└── Ingresos Institucionales                 (is_group=1)
    ├── Subsidios / Donaciones / Recaudación institucional
```

Items solo en hojas (`is_group = 0`).

---

## Scenario: pilares de ingreso son nodos

Given `All Item Groups` y la migración jerárquica
When corre el seed
Then los 4 pilares tienen `is_group = 1` y padre `All Item Groups`
And no tienen Items directos (`item_group` del pilar vacío)

---

## Scenario: ítems de socio en hojas correctas

Given `ICDPE-CUOTA-SOCIAL` y cargos (`ICDPE-MULTA`, `RECARGO-MORA`, …)
When corre la migración
Then la cuota queda en `Cuotas sociales`
And multa / cargo / mora quedan en `Cargos extras y mora`

---

## Scenario: aranceles por deporte / fitness

Given ítems `ICDPE-BASQUET-*`, `ICDPE-FUTBOL-*`, `ICDPE-GYM-*`, etc.
When corre la migración
Then cada uno queda en la hoja de su deporte o actividad fitness
And el padre de esas hojas es `Deportes` o `Fitness y actividades`

---

## Scenario: seed idempotente

Given jerarquía ya aplicada
When se vuelve a ejecutar
Then no hay error de llave duplicada y el mapeo se mantiene

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Árbol + migración | `finance/setup/icdpe_income_item_groups.py` |
| Patch (idempotente) | `patches/v1_0/migrate_ingresos_item_groups.py` + `_jerarquia.py` |
| Tests | `tests/test_catalogo_ingresos_item_groups.py` |
| Matriz item→hoja | `specs/catalogo_ingresos_matriz_mapeo.md` |
| Matriz | `specs/catalogo_ingresos_matriz_mapeo.md` |
