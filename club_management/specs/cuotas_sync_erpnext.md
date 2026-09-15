# Spec: Sincronización cuotas sociales → ERPNext

Al guardar montos de cuota social (panel Secretaría o `Club Settings`), el sistema debe mantener alineados **Item**, **Item Price** y **Subscription Plan**.

**Relacionado:** `secretaria_workspace_listas.md`, `cuotas_sociales_suscripcion.md`  
**Gap actual:** `save_cuotas_sociales` solo persiste `Club Settings`.

---

## Scenario: guardar cuotas actualiza ítem único y precio referencia

Given `Club Settings.cuotas_categoria` con 6 categorías y montos distintos
And ítem único `CLUB-Cuota-Social-Base`
When Secretaría llama `save_cuotas_sociales` con montos válidos
Then persiste filas en `Club Settings`
And actualiza `Item.standard_rate` del ítem al monto de categoría `Activo` (tarifa referencia del ítem)
And actualiza o crea `Item Price` en `Standard Selling` con ese monto referencia
And actualiza `Subscription Plan.cost` (Fixed Rate) si `price_determination = Fixed Rate`
  **o** documenta que el plan usa monto por categoría vía facturación manual (ver nota abajo).

**Nota de diseño:** una suscripción ERPNext = un plan = un ítem. El monto real por socio depende de `resolve_cuota_social(socio)` al facturar. El sync no debe sobrescribir montos por categoría en un solo ítem; solo asegura existencia del ítem/plan y tarifa referencia.

---

## Scenario: sync explícito post-guardado

Given cambio de monto de categoría `Menor`
When se ejecuta `sync_cuotas_sociales_club()` tras guardar
Then todas las filas `cuotas_categoria` tienen `item = CLUB-Cuota-Social-Base`
And `Club Settings.item_cuota_social` apunta al mismo ítem.

---

## Scenario: montos inválidos

Given `save_cuotas_sociales` con monto ≤ 0 para cualquier categoría
Then error de validación y no se guarda.

---

## Scenario: Vitalicio excluido

Given categoría `Vitalicio` no está en `cuotas_categoria` (cuota 0 por regla de negocio)
When se sincroniza
Then no se exige fila Vitalicio en la tabla.

---

## Artefactos esperados

| Artefacto | Cambio |
|-----------|--------|
| `secretaria_workspace_panel.save_cuotas_sociales_payload` | llamar sync ERPNext |
| `members/services/cuotas_sociales_setup.py` | reutilizar |
| Tests | `members/tests/test_cuotas_sync_erpnext.py` |
