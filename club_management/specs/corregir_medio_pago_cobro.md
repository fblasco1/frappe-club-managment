# Spec: Corregir medio de pago de un cobro ya registrado

Secretaría a veces elige mal el **medio de pago** al registrar el cobro
(p. ej. Efectivo en lugar de Transferencia). En ERPNext el `Payment Entry`
submitted no permite editar `mode_of_payment` a mano, y cambiarlo a ciegas
rompe la coherencia con la cuenta contable del medio.

**Relacionado:** `historial_pagos_socio.md`, `recibo_pago_escpos.md`,
`cobro_multi_factura_medios_mixtos.md`

---

## Decisión (implementada)

**Acción Desk «Corregir medio de pago»** sobre un `Payment Entry` submitted:

1. Solo roles `Secretaria` / `System Manager`.
2. Diálogo: medio nuevo + **motivo** obligatorio.
3. Cancela el PE original (sin tocar las Sales Invoice: vuelven a quedar
   con saldo y se reimputan al toque).
4. Crea y submittea un PE nuevo con el mismo monto, fecha, facturas e
   imputaciones, pero con el `mode_of_payment` (y cuenta `paid_to`) correctos.
5. Deja un `Comment` en el PE nuevo y en el cancelado enlazando ambos + motivo.
6. Refresca historial / saldo; ofrece reimprimir el ticket del PE nuevo.

### Por qué no editar el campo en el PE submitted

- El medio define la cuenta de caja/banco. Cambiar solo la etiqueta deja
  informes de recaudación y asientos desalineados.
- Cancel + recrear es el patrón estándar de ERPNext y deja auditoría clara.

### Fuera de alcance de este corte

- Corregir monto, fecha o facturas imputadas (sigue siendo cancelar cobro
  manualmente / soporte).
- Cobros Supervielle conciliados automáticamente (gate distinto).

---

## Scenario: Secretaría corrige Efectivo → Transferencia

Given un PE submitted del socio por $10.000 en `Cash`
When Secretaría elige **Corregir medio de pago** → `Wire Transfer` con motivo
Then el PE original queda cancelado
And existe un PE nuevo submitted con el mismo total e imputaciones
And el medio del nuevo es `Wire Transfer`
And el historial muestra el cobro vigente con el medio corregido
And quedan comentarios de auditoría en el PE cancelado y en el nuevo
And la API puede devolver el recibo del PE nuevo para reimprimir.

## Scenario: mismo medio rechazado

Given un PE submitted en `Cash`
When se pide corregir a `Cash` otra vez
Then error de validación
And el PE original sigue submitted.

## Scenario: cobro Supervielle no corregible por esta vía

Given un PE vinculado a un `Payment Log` del gateway
When Secretaría intenta corregir el medio
Then error de validación
And el PE no se cancela.

## Scenario: sin permiso

Given un usuario sin rol Secretaría / System Manager
When intenta corregir el medio
Then recibe error de permiso
And no se cancela ni crea ningún PE.

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/corregir_medio_pago_cobro.md` |
| Servicio | `members/services/cobranza_manual.py` (`corregir_medio_pago_cobro`) |
| API | `members/api/cobranza_desk.py` |
| UI | `members/doctype/socio/socio.js` (historial) |
| Tests | `members/tests/test_corregir_medio_pago_cobro.py` |
