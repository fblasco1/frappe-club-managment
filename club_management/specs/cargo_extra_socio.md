# Spec: Cargos extra al socio

Secretaría debe poder crear cargos como **Cuota Federativa**, **Multa FEBAMBA**, **Viaje a Santa Fe**, etc., con cobro **único** o **recurrente** en un período.

**Relacionado:** `cobranza_periodica_mensual.md`, `mvp_operacion_secretaria_sin_pagos.md`

---

## DocType: `Cargo Socio`

| Campo | Tipo | Reqd | Notas |
|-------|------|------|-------|
| `socio` | Link → Socio | sí | |
| `titulo` | Data | sí | Ej. «Viaje a Santa Fe» |
| `tipo_cargo` | Select | sí | `Cuota Federativa` / `Multa` / `Viaje` / `Otro` |
| `modo_cobro` | Select | sí | `Unico` / `Recurrente` |
| `item` | Link → Item | sí | Servicio ERPNext (`is_stock_item = 0`) |
| `monto` | Currency | sí | |
| `fecha_desde` | Date | sí | Inicio vigencia |
| `fecha_hasta` | Date | no | Obligatorio si `Recurrente`; fin de período |
| `estado` | Select | sí | `Pendiente` / `Facturado` / `Cancelado` |
| `sales_invoice` | Link → Sales Invoice | no | Para modo `Unico` tras facturar |
| `observaciones` | Small Text | no | |

**Permisos:** `Secretaria` create/read/write; sin delete (cancelar → `Cancelado`).

---

## Scenario: Secretaría crea cargo único

Given `Socio` `Activo` con `Customer`
When Secretaría crea `Cargo Socio` con `modo_cobro = Unico`, monto 15000, ítem válido
Then queda `estado = Pendiente`
When ejecuta **Facturar cargo** (acción Desk o API `facturar_cargo_socio`)
Then se crea `Sales Invoice` submitted con una línea
And `Cargo Socio.estado = Facturado` y `sales_invoice` poblado
And `Socio.saldo_deuda` actualizado.

---

## Scenario: cargo recurrente incluido en deuda mensual

Given `Cargo Socio` `Recurrente` con `fecha_desde` ≤ hoy ≤ `fecha_hasta`
And `estado = Pendiente`
When corre `generar_deuda_mensual_socios`
Then la factura mensual incluye una línea con ese monto e ítem
And el cargo permanece `Pendiente` (se factura cada mes hasta `fecha_hasta`) **o** se registra hijo/log por mes (elegir: **línea en factura mensual sin cambiar estado hasta fin de período**).

---

## Scenario: cancelar cargo pendiente

Given `Cargo Socio` `Pendiente` sin factura
When Secretaría cancela el cargo
Then `estado = Cancelado` y no entra en próxima deuda mensual.

---

## Scenario: catálogo de ítems sugeridos

Given ítems ICDPE `ICDPE-CUOTA-FEDERATIVA-*` existentes en el sitio
When Secretaría elige tipo `Cuota Federativa`
Then el formulario sugiere ítems del grupo federativo (client script opcional).

---

## Scenario: aislamiento entre socios

Given cargo de Socio A
When Socio B consulta sus cargos
Then no ve filas de A (`User Permission` / filtro por socio en API portal futuro).

---

## UI Desk

- Formulario `Cargo Socio` en módulo Members.
- Botón en formulario `Socio`: **Nuevo cargo extra** (abre `Cargo Socio` con `socio` precargado).
- Lista relacionada en Socio (custom o dashboard).

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| DocType JSON/PY | `members/doctype/cargo_socio/` |
| Servicio | `members/services/cargo_socio.py` |
| API | `members/api/cobranza_desk.py` o `socio_operaciones_desk.py` |
| Tests | `members/doctype/cargo_socio/test_cargo_socio.py` |
