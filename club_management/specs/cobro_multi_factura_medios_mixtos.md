# Spec: Cobro multi-factura y medios mixtos

Secretaría registra cobros desde el formulario `Socio` eligiendo **una o más facturas enteras** pendientes y pagando con **un medio** (simple) o **varios medios** (mixto: p. ej. efectivo + transferencia).

**Modelo de facturación:** cada concepto (cuota social, arancel-actividad, cuota federativa, cargo extra, etc.) es una `Sales Invoice` distinta. **Generar cargo** crea una SI por concepto pendiente del período.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `registrar_cobro_fecha.md`, `recibo_pago_escpos.md`

---

## Scenario: Generar cargo emite una factura por concepto

Given un `Socio` Activo con cuota social e inscripción activa con arancel
And no hay facturas del período para esos ítems
When Secretaría ejecuta **Generar cargo**
Then se crean al menos dos `Sales Invoice` submitted (cuota y arancel)
And cada una tiene una sola línea de concepto
And todas comparten el mismo `periodo_cobro`
And `Socio.saldo_deuda` es la suma de los outstanding.

---

## Scenario: Generar cargo no bloquea si ya hay otra factura del período

Given ya existe la factura de cuota del período
And falta facturar el arancel
When Secretaría ejecuta **Generar cargo**
Then se crea solo la factura del arancel pendiente
And no se duplica la cuota.

---

## Scenario: Registrar cobro de varias facturas con un medio (simple)

Given dos `Sales Invoice` pendientes del socio (cuota y arancel)
When Secretaría selecciona ambas y un solo medio (p. ej. Efectivo) por el total
Then se crea **un** `Payment Entry` submitted con ese medio
And ambas facturas quedan con `outstanding_amount = 0`
And `Socio.saldo_deuda` se actualiza
And `reference_no` del PE no supera 140 caracteres (lista larga de SI va en `remarks`).

---

## Scenario: Registrar cobro mixto (efectivo + transferencia)

Given facturas pendientes cuya suma de outstanding es 15000
When Secretaría selecciona esas facturas
And carga medios: Efectivo 10000 + Transferencia 5000
Then se crean **dos** `Payment Entry` (uno por medio)
And la suma de montos de los PE es 15000
And las facturas seleccionadas quedan saldadas
And la asignación entre facturas es FIFO por orden de selección/listado.

---

## Scenario: Suma de medios debe coincidir con facturas

Given facturas seleccionadas por total 10000
When los medios suman 9000 o 11000
Then error de validación
And no se crea ningún `Payment Entry`.

---

## Scenario: Debe seleccionar al menos una factura y un medio

Given Secretaría abre **Registrar cobro**
When confirma sin facturas o sin montos de medio > 0
Then error de validación.

---

## Scenario: Compatibilidad cobro unitario

Given una sola factura pendiente
When se llama `registrar_cobro_manual(socio, sales_invoice, mode_of_payment=…)`
Then se comporta como cobro simple (un PE, factura saldada).

---

## Scenario: Fecha de cobro en cobro compuesto

Given cobro multi-factura o mixto
When se indica `posting_date`
Then todos los PE usan esa fecha (mismas reglas que `registrar_cobro_fecha.md`: default hoy, no futura).

---

## Scenario: UI Desk — multiselect y medios

Given un `Socio` con varias facturas pendientes
When Secretaría abre **Registrar cobro**
Then puede marcar varias facturas (multiselect)
And puede cargar uno o más medios con monto
And al confirmar se llama a la API de cobro compuesto.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cobro_multi_factura_medios_mixtos.md` |
| Servicio | `members/services/cobranza_manual.py` |
| API | `members/api/cobranza_desk.py` |
| JS | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_cobro_multi_factura_medios_mixtos.py` |
| Tests UI | `members/tests/test_cobro_multi_factura_ui.py` |
