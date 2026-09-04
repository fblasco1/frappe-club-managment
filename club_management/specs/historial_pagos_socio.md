# Spec: Historial de pagos en formulario Socio

Secretaría ve en el perfil `Socio` los **últimos pagos** registrados (Payment Entry) para informar al socio.

**Relacionado:** `cobro_multi_factura_medios_mixtos.md`, `deuda_socio_desk.md`

---

## Scenario: listar historial de pagos del socio

Given un `Socio` con uno o más `Payment Entry` submitted contra sus facturas
When Secretaría consulta el historial
Then recibe filas ordenadas por fecha desc con: **fecha**, **medio**, **concepto**, **período**, `payment_entry`
And el **concepto** / **período** salen de la factura principal (no ajuste `*-MORA` si hay otra)
And cada fila incluye `detalle.facturas` (nombre, período, concepto, total, imputado) y datos del PE
And solo incluye pagos de ese socio (sin cruzar a otro).

---

## Scenario: etiqueta de concepto legible

Given un pago imputado a una SI de **arancel de actividad**
When Secretaría ve el historial
Then **concepto** muestra la descripción del producto (`Item.item_name`), p. ej. `ARANCEL MENSUAL - BASQUET/MASCULINO/MINIBASQUET`
And no el genérico `Arancel actividad`.

Given un pago imputado a una SI de **cuota social**
When Secretaría ve el historial
Then **concepto** es `CUOTA SOCIAL {CATEGORIA}` usando la categoría del socio (p. ej. `CUOTA SOCIAL ACTIVO`)
And no el genérico `Cuota social`.

---

## Scenario: panel en Desk con Ver detalle

Given Secretaría abre el formulario `Socio`
When carga el panel de historial
Then ve una sección **Historial de pagos** debajo de la deuda
And la tabla muestra columnas: **Fecha**, **Medio**, **Concepto**, **Período**, **Ver detalle**
And **Ver detalle** abre un modal con las facturas del cobro y el Payment Entry asociado
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
