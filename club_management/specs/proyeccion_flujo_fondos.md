# Spec: Proyección de flujo de fondos

El Tesorero, el día 1 del mes (o cualquier `as_of_date`), ve si la liquidez proyectada alcanza para cubrir obligaciones críticas en los primeros N días (default **5**).

**Relacionado:** `rol_tesoreria_permisos.md`, `carga_rapida_ingreso_egreso.md`

**Proyección Cobros Plus:** se asume 1.er vencimiento / ola de cobranza el **día 10** del mes
(cuota social **y** aranceles deportivos con ese `due_date`). Segundo hito de mora proyectada: **día 20**.

---

## Scenario: saldo caja y bancos

Given cuentas Cash/Bank con GL Entry no cancelados
When Tesorería solicita la proyección
Then `saldo_caja_bancos` es la suma `debit - credit` de esas cuentas (PostgreSQL).

---

## Scenario: salidas en ventana de N días

Given Purchase Invoices submitted con `outstanding_amount > 0` y `due_date` en `[as_of, as_of+N]`
When se calcula la proyección con `ventana_dias = 5`
Then `pagos_comprometidos` suma esos outstanding
And se desglosan por `club_concepto` cuando existe.

---

## Scenario: obligaciones críticas Personal + Estructura

Given PI de categoría `Personal` y `Estructura` en la ventana
When se calcula
Then `obligaciones_criticas` incluye solo esas categorías
And el semáforo `liquidez_alcanza` es True si `saldo_caja_bancos + cobros_proyectados_ventana >= obligaciones_criticas`.

---

## Scenario: cobros proyectados día 10 (cuota + arancel)

Given Sales Invoices outstanding (cuota y/o arancel) con `due_date` = día 10 del mes de `as_of_date`
When `as_of_date` es día 1 y la ventana es 5
Then esos cobros **no** entran en `cobros_proyectados_ventana` (día 10 > día 5)
And sí aparecen en `cobros_proyectados_mes` por el outstanding (sin mora aún).

---

## Scenario: cobros mes post día 10 / día 20 con mora

Given SI outstanding con `due_date` = día 10 del mes
When `as_of_date` es posterior al día 10 y ≤ día 20
Then `cobros_proyectados_mes` sigue listando esa ola (aunque `due_date` < `as_of`)
And el monto se recalcula con el recargo del 1.er vencimiento (`recargo_post_vencimiento_pct`, default 10 %)
When `as_of_date` es posterior al día 20
Then el monto incluye además el recargo del 2.º hito (`recargo_mes_vencido_pct`, default 5 %).

---

## Scenario: permiso Tesorería

Given usuario Secretaria sin Tesoreria
When ejecuta el Script Report o la API
Then PermissionError.

---

## Scenario: Desk no llama slug sin argumento (render Query Report)

Given el bundle de navegación del club (`club_desk_navigation.js`, `inicio_workspace.js`)
When se resuelve el workspace activo o se detecta Inicio
Then **nunca** se invoca `frappe.router.slug()` sin el nombre a slugificar
And el Query Report «Proyeccion Flujo de Fondos» puede completar la carga (deja de quedar en «Cargando…»).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `finance/services/flujo_fondos.py` |
| API | `finance/api/tesoreria_desk.py` |
| Report | `finance/report/proyeccion_flujo_de_fondos/` |
| Workspace | `finance/workspace/tesoreria/` |
| Tests | `tests/test_flujo_fondos.py` |
