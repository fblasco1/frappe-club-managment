# Spec: Webhook Cobros Plus (Supervielle) — Notificación de pago

Given/When/Then scenarios for receiving callbacks from Banco Supervielle (Cobros Plus).
Implementation must follow TDD after this spec.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`

---

## Scenario: Validación de autenticidad por hash inverso

Given un JSON recibido desde Cobros Plus con un campo `"hash"`
And el Single `Cobros Plus Settings` contiene la `secret_key`
When el webhook valida el mensaje
Then recalcula el hash concatenando **todos los valores** del JSON recibido en el **orden exacto**
And excluye el valor del campo `"hash"`
And agrega al final la `secret_key`
And calcula SHA-256 (hex)
And si el hash no coincide, retorna HTTP 403 y registra el intento en `frappe.log_error`

---

## Scenario: Idempotencia ante reintentos del banco

Given un pago ya conciliado (existe un Payment Entry submitted) contra la misma `Sales Invoice`
When el banco reintenta la notificación (mismo `cod_trx` / misma referencia)
Then el webhook no crea un segundo pago
And responde HTTP 200 OK para evitar reintentos

---

## Scenario: Conciliación de pago y activación del socio

Given un JSON válido con identificador de deuda (por ejemplo `cod_trx`)
And existe una `Sales Invoice` asociada a esa referencia
When el webhook procesa el pago aprobado
Then crea y submitea un `Payment Entry` contra esa factura (si corresponde)
And si el `Socio` asociado estaba "Moroso" o "Pendiente", lo pasa a "Activo"
And dispara la habilitación/generación del Carné Digital QR (si aplica)
And responde HTTP 200 OK con acuse de recibo

