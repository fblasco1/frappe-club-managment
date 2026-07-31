# Spec: Historial de pagos en formulario Socio

Secretaría ve en el perfil `Socio` los **últimos pagos** registrados (Payment Entry) para informar al socio.

**Relacionado:** `cobro_multi_factura_medios_mixtos.md`, `deuda_socio_desk.md`

---

## Scenario: listar historial de pagos del socio

Given un `Socio` con uno o más `Payment Entry` submitted contra sus facturas
When Secretaría consulta el historial
Then recibe filas ordenadas por fecha desc con: fecha, medio de pago, monto, facturas referenciadas, nombre del PE
And solo incluye pagos de ese socio (sin cruzar a otro).

---

## Scenario: panel en Desk

Given Secretaría abre el formulario `Socio`
When carga el panel de historial
Then ve una sección **Historial de pagos** debajo de la deuda
And puede copiar un resumen de texto de los últimos pagos.

---

## Scenario: sin pagos

Given un `Socio` sin cobros
When abre el historial
Then el panel indica que no hay pagos registrados.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/historial_pagos_socio.md` |
| Servicio | `members/services/cobranza_manual.py` (`list_historial_pagos_socio`) |
| API | `members/api/cobranza_desk.py` |
| JS | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_historial_pagos_socio.py` |
