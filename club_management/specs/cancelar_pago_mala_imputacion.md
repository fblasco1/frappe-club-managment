# Spec: Cancelar pago por mala imputación

Secretaría a veces registra un cobro contra las facturas equivocadas
(p. ej. cuota social + mora cuando el dinero correspondía a otro concepto).
El `Payment Entry` submitted no se edita: se **cancela** y las facturas
vuelven a quedar con saldo para cobrarlas de nuevo.

**Relacionado:** `historial_pagos_socio.md`, `corregir_medio_pago_cobro.md`,
`cancelar_factura_venta_impaga.md`

---

## Decisión

**Acción Desk «Cancelar pago»** en el historial del `Socio`, sobre un
`Payment Entry` submitted:

1. Solo roles `Secretaria` / `System Manager`.
2. El cobro tiene que ser del socio abierto en el formulario.
3. Diálogo con **motivo** obligatorio (mala imputación u otro error de caja).
4. Cancela el PE. No crea otro. Las Sales Invoice imputadas recuperan
   su `outstanding_amount`.
5. Deja un `Comment` en el PE cancelado con el motivo.
6. Recalcula `Socio.saldo_deuda` y refresca el historial (el cobro cancelado
   deja de listarse).
7. Cobros vinculados a `Payment Log` (Supervielle / Cobrand) no se cancelan
   por esta vía.

Fuera de alcance: reimputar el mismo dinero en el acto (Secretaría usa
**Registrar cobro** sobre las facturas correctas) y anular la factura de mora
generada al cobro (sigue el flujo de cancelar factura impaga).

---

## Scenario: Secretaría cancela un cobro mal imputado

Given un PE submitted del socio que imputa una factura por $10.000
When Secretaría elige **Cancelar pago** con motivo
Then el PE queda cancelado (`docstatus=2`)
And la factura vuelve a tener `outstanding_amount` igual a su total
And `saldo_deuda` del socio incluye ese saldo
And el historial ya no muestra ese PE
And el PE cancelado tiene un comentario con el motivo.

## Scenario: motivo obligatorio

Given un PE submitted
When se pide cancelar con motivo vacío
Then error de validación
And el PE sigue submitted
And la factura sigue saldada.

## Scenario: cobro de otro socio

Given un PE submitted del socio A
When se pide cancelarlo indicando el socio B
Then error de validación
And el PE de A sigue submitted.

## Scenario: cobro de pasarela

Given un PE vinculado a un `Payment Log` del gateway
When Secretaría intenta cancelarlo
Then error de validación
And el PE no se cancela.

## Scenario: sin permiso

Given un usuario sin rol Secretaría / System Manager
When intenta cancelar el pago
Then recibe error de permiso
And el PE sigue submitted.

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cancelar_pago_mala_imputacion.md` |
| Servicio | `members/services/cobranza_manual.py` (`cancelar_pago_mala_imputacion`) |
| API | `members/api/cobranza_desk.py` (`cancelar_pago`) |
| UI | `members/doctype/socio/socio.js` (historial) |
| Tests | `members/tests/test_cancelar_pago_mala_imputacion.py` |
