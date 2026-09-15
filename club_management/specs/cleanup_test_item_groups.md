# Spec: Eliminar Item Groups de fixtures ERPNext (`_Test Item Group*`)

En sitios de desarrollo a veces quedan Item Groups e Items de tests de ERPNext
bajo `All Item Groups` (p. ej. `_Test Item Group`, `_Test Item Group B`, …).

**Relacionado:** `cleanup_residual_item_groups.md`

---

## Scenario: limpia grupos `_Test Item Group*`

Given Item Groups cuyo `name` empieza con `_Test Item Group`
When corre `run_cleanup_test_item_groups`
Then se eliminan los ítems cuyo código empieza con `_Test` en esos grupos
And cualquier otro ítem se reubica a un grupo hoja de parking/Products
And los Item Groups `_Test Item Group*` quedan eliminados (o sin hijos/ítems)

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Lógica | `finance/setup/cleanup_test_item_groups.py` |
| Patch | `patches/v1_0/cleanup_test_item_groups.py` |
| Tests | `tests/test_cleanup_test_item_groups.py` |
