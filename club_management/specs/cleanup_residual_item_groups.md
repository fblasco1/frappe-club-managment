# Spec: Limpieza de Item Groups residuales (ingresos/egresos)

Tras la jerarquía de ingresos y egresos, quedan grupos planos bajo
`All Item Groups` que ya no deben mostrarse en el catálogo operativo.

**Relacionado:** `catalogo_egresos_item_groups.md`, `catalogo_ingresos_item_groups.md`

---

## Residuales

| Grupo residual | Acción |
|----------------|--------|
| `ICDPE / Finanzas egresos` | Reasignar ítems disabled a hojas de egreso; eliminar el grupo si queda vacío |
| `Cuotas Sociales` | Reasignar ítems a `Cuotas sociales` (hoja del pilar Socios); eliminar el grupo residual |

No se borran Items (integridad de documentos históricos); solo se mueve `item_group`
y se elimina/archiva el Item Group vacío.

El seed de egresos **deja de recrear** `ICDPE / Finanzas egresos` bajo la raíz.
El bootstrap de suscripciones usa `Cuotas sociales` (no el residual).

---

## Scenario: egresos residuales van a hojas

Given ítems `ICDPE-FIN-SUELDOS`, `ICDPE-FIN-IMPUESTOS`, … en `ICDPE / Finanzas egresos`
When corre `cleanup_residual_item_groups`
Then cada uno queda en su hoja de egreso (Remuneraciones, Impuestos, …)
And siguen `disabled = 1` si ya lo estaban
And el Item Group `ICDPE / Finanzas egresos` no existe o no cuelga de `All Item Groups` con ítems

---

## Scenario: Cuotas Sociales residual → Cuotas sociales

Given ítems en el Item Group residual `Cuotas Sociales` (padre `All Item Groups`)
When corre la limpieza
Then esos ítems tienen `item_group = Cuotas sociales`
And el residual `Cuotas Sociales` se elimina si quedó vacío
And la hoja canónica `Cuotas sociales` bajo Socios permanece

---

## Scenario: idempotente

Given la limpieza ya aplicada
When se vuelve a ejecutar
Then no falla

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Lógica | `finance/setup/cleanup_residual_item_groups.py` |
| Patch | `patches/v1_0/cleanup_residual_item_groups.py` |
| Tests | `tests/test_cleanup_residual_item_groups.py` |
