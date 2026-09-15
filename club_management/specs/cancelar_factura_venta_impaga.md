# Spec: Cancelar Factura de Venta impaga y regenerar cargo

Secretaría puede **cancelar** una `Sales Invoice` de cobranza **sin cobros**
vinculada al socio, corregir la inscripción (arancel u otro error) y volver a
**Generar cargo** del mismo período.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `sales_invoice_cancel_postgres.md`

---

## Scenario: cancelar factura impaga

Given un socio con una `Sales Invoice` submitted (`docstatus = 1`)
And `outstanding_amount` = `grand_total` (sin Payment Entry aplicado)
And la factura está vinculada a ese socio
When Secretaría ejecuta **Cancelar factura impaga** desde el formulario Socio
Then la factura queda `docstatus = 2` (Cancelled)
And `Socio.saldo_deuda` se recalcula sin esa factura.

---

## Scenario: no cancelar factura cobrada o parcial

Given una `Sales Invoice` del socio con `outstanding_amount` < `grand_total`
When Secretaría intenta cancelarla
Then recibe `ValidationError`
And la factura permanece submitted.

---

## Scenario: no cancelar factura de otro socio

Given una `Sales Invoice` vinculada al socio A
When Secretaría intenta cancelarla indicando socio B
Then recibe error de validación o permiso
And la factura no se cancela.

---

## Scenario: regenerar cargo tras cancelar

Given se canceló la factura del período `MM/YYYY` del socio
And se corrigió el arancel en la inscripción activa
When Secretaría ejecuta **Generar cargo**
Then se crea una nueva `Sales Invoice` submitted del mismo `periodo_cobro`
And las líneas reflejan los aranceles/cuotas actuales.

---

## Scenario: botón Desk

Given Secretaría abre el formulario `Socio`
When mira el grupo **Cobranza manual**
Then ve el botón **Cancelar factura impaga**
And al usarlo elige entre facturas submitted con saldo completo (impagas)
And confirma antes de cancelar.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cancelar_factura_venta_impaga.md` |
| Servicio | `members/services/cobranza_manual.py` |
| API | `members/api/cobranza_desk.py` |
| UI | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_cancelar_factura_venta_impaga.py` |
