# Spec: Deuda pendiente visible en formulario Socio

Secretaría debe ver en cada `Socio` el **saldo impago** y el **detalle de conceptos** que lo componen.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `cargo_extra_socio.md`, `cobranza_periodica_mensual.md`

---

## Scenario: panel de deuda en Desk

Given un `Socio` con facturas ERPNext impagas y/o cargos extra pendientes
When Secretaría abre el formulario `Socio`
Then ve una sección **Deuda pendiente** con el total (`saldo_deuda`)
And una tabla con conceptos: facturas submitteadas con saldo (líneas) y cargos `Cargo Socio` pendientes sin facturar.

---

## Scenario: generar cargo manual incluye cargos extra recurrentes

Given `Club Settings.incluir_cargos_extra_en_deuda_mensual = 1`
And un `Cargo Socio` recurrente vigente en estado `Pendiente`
When Secretaría ejecuta **Generar cargo** en el formulario `Socio`
Then la `Sales Invoice` incluye cuota/aranceles y el cargo extra recurrente
And `Socio.saldo_deuda` refleja el saldo ERPNext.

---

## Scenario: facturar cargo único actualiza deuda

Given un `Cargo Socio` `Unico` en `Pendiente`
When Secretaría ejecuta **Facturar cargo**
Then se crea y confirma la `Sales Invoice` sin error en PostgreSQL
And el cargo aparece en el detalle de deuda del socio.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio detalle | `members/services/cobranza_manual.py` |
| API Desk | `members/api/cobranza_desk.py` |
| UI Socio | `members/doctype/socio/socio.js` |
| Parche PG | `integrations/payment_ledger_postgres.py` |
| Tests | `members/tests/test_deuda_socio_desk.py` |
