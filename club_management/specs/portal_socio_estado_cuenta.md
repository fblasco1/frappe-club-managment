# Portal del socio — Estado de cuenta (BL-6d)

**Backlog:** extensión del portal autenticado (ver `portal_socio_alcance.md`)
**Relacionado:** `deuda_socio_desk.md`, `historial_pagos_socio.md`, `portal_socio_perfil.md`, `portal_socio_inscripcion.md`

Expone al socio autenticado su **deuda exigible** y los **últimos comprobantes de pago**.
La identidad sale solo de `frappe.session.user`. Cobranza online (Cobrand / Supervielle)
sigue siendo épica aparte: este corte lee `Sales Invoice` y `Payment Entry` ya persistidos.

## Decisiones de contrato

- Endpoint autenticado `@frappe.whitelist()`: `get_estado_cuenta_socio()`.
- Guest, usuario sin `Socio` único vinculado, o sin rol `Socio` → `frappe.PermissionError` (HTTP 403).
- Ningún parámetro del cliente elige el socio: no se acepta `socio`, email ni DNI para el alcance.
- Facturas: `Sales Invoice` del socio con `docstatus = 1` y `outstanding_amount > 0`.
  Borrador (`0`) y canceladas (`2`) quedan fuera.
- Pagos: últimos 5 `Payment Entry` submitted imputados a facturas de ese socio.
- La respuesta es JSON serializable (fechas como string ISO, montos como número).

## Scenario: socio autenticado ve su deuda y pagos

Given un Website User con rol `Socio` y un único `Socio` vinculado
And el socio tiene facturas presentadas con saldo y pagos submitted
When llama `get_estado_cuenta_socio`
Then recibe `facturas_pendientes` con `name`, `posting_date`, `due_date`,
`outstanding_amount` y `concepto` (descripción de línea o rubro)
And recibe `pagos_recientes` (máximo 5) con fecha, monto, método de pago y `recibo_url`.

## Scenario: Guest y sesión inválida fallan cerrados

Given Guest, o un usuario sin `Socio` vinculado
When llama `get_estado_cuenta_socio`
Then recibe `frappe.PermissionError`.

## Scenario: aislamiento entre dos socios

Given los usuarios autenticados A y B vinculados a socios distintos
And A tiene una factura pendiente que B no tiene
When B consulta el estado de cuenta
Then no ve facturas ni pagos de A.

## Scenario: excluye borrador y canceladas

Given un socio autenticado con una SI en borrador, una cancelada y una presentada con saldo
When consulta el estado de cuenta
Then solo aparece la factura presentada con `outstanding_amount > 0`.

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/portal_socio_estado_cuenta.md` (este archivo) |
| API | `members/api/portal_finance.py` |
| Tests | `tests/test_portal_finance.py` |
