# Spec: Payment Log (IDs inmutables — Cobrand / Banco Supervielle)

**Estado:** implementación inicial (2026-09-07). Canal: Cobrand + Banco Supervielle. **SIRO no aplica.**

El webhook legado (`supervielle_webhook.py`) hoy busca la factura por `reference`. Este DocType es el mapa `gateway_transaction_id` → factura; **no** cambia el contrato de hash SHA-256 ya especificado.

La publicación de Botón de Pago (`specs/supervielle_boton_pago.md`) **también** escribe un Payment Log por intento (`provider = Banco Supervielle`, snapshot request/response en `payload_json`).

**Ruta en Bench:** `apps/club_management/club_management/specs/payment_log.md`

**DocType:** `Payment Log` (módulo Finance).  
**Servicio:** `club_management.finance.services.payment_log.record_gateway_transaction`.

---

## Objetivo

Cada transacción del gateway se persiste **una sola vez** en `Payment Log` para:

1. Idempotencia de webhooks (mismo ID → no duplicar Payment Entry).
2. Inmutabilidad del ID de transacción (nunca reutilizar ni sobrescribir para otro pago).
3. Trazabilidad hacia `Sales Invoice` / `Payment Entry` / `Socio` cuando se concilié.

El webhook legado (`supervielle_webhook.py`) hoy busca la factura por `reference`. Este DocType es el mapa `gateway_transaction_id` → factura; **no** cambia el contrato de hash SHA-256 ya especificado.

---

## Scenario: alta con ID único

Given un `gateway_transaction_id` que no existe en Payment Log
And un `provider` igual a `Cobrand` o `Banco Supervielle`
When el servicio registra el evento de gateway
Then se crea un Payment Log con ese ID
And el estado inicial es `Recibido`
And el documento queda persistido

---

## Scenario: SIRO no es un proveedor válido

Given un intento de registro con `provider = SIRO`
When el servicio o el DocType validan el documento
Then se rechaza con `ValidationError`
And no se inserta ningún Payment Log

---

## Scenario: idempotencia — mismo ID, mismo pago

Given ya existe un Payment Log con `gateway_transaction_id = X` y `gateway_reference = R`
When llega de nuevo el mismo ID `X` con la misma referencia `R`
Then no se inserta un segundo registro
And se devuelve el documento existente
And no se modifica `gateway_transaction_id` ni `gateway_reference`

---

## Scenario: no reutilizar ID en otro pago

Given ya existe un Payment Log con `gateway_transaction_id = X` y `gateway_reference = R1`
When se intenta registrar el mismo ID `X` contra una referencia distinta `R2`
Then se rechaza con `ValidationError`
And el registro original no se modifica

---

## Scenario: campos de pago inmutables tras insertar

Given un Payment Log existente
When se intenta cambiar `gateway_transaction_id`, `provider` o `gateway_reference`
Then se rechaza con `ValidationError`
And no se permite borrar el documento (`on_trash`)

---

## Scenario: el estado puede avanzar sin tocar el ID

Given un Payment Log en estado `Recibido`
When se actualiza `status` a `Conciliado` (p. ej. tras crear el Payment Entry)
Then el cambio de estado se acepta
And `gateway_transaction_id` permanece igual

---

## Scenario: Socio no lee Payment Log; Tesorería sí

Given un usuario con rol `Socio`
When consulta permisos de `Payment Log`
Then no tiene lectura ni escritura

Given un usuario con rol `Tesoreria`
When consulta permisos de `Payment Log`
Then tiene lectura y no tiene create/write/delete

Given `System Manager`
When registra un evento vía el servicio (o Desk)
Then puede crear; no puede borrar ni alterar el ID

---

## Scenario: no hay endpoints inventados

Given que la documentación de API Cobrand/Supervielle no está cargada
When se implementa Payment Log
Then no se añaden llamadas HTTP a URLs de cobro
And el hash SHA-256 del webhook existente no cambia
And no se documentan flujos SIRO

---

## Campos (mínimo)

| Campo | Tipo | Notas |
|-------|------|--------|
| `gateway_transaction_id` | Data unique, reqd, set_only_once | ID del gateway; clave de idempotencia |
| `provider` | Select `Cobrand` / `Banco Supervielle` | Nunca SIRO |
| `status` | Select `Recibido` / `Conciliado` / `Rechazado` | Mutable (avance de conciliación) |
| `gateway_reference` | Data, set_only_once | Referencia cruda (`cod_trx` / `reference`) |
| `sales_invoice` | Link Sales Invoice, set_only_once | Opcional hasta conciliar |
| `payment_entry` | Link Payment Entry, set_only_once | Opcional |
| `socio` | Link Socio, set_only_once | Opcional |
| `amount` | Currency | Opcional |
| `currency` | Data | Default `ARS` |
| `payload_json` | JSON, set_only_once | Snapshot de auditoría; no modela la API |
| `received_at` | Datetime | Momento de recepción |

---

## Fuera de alcance (esta entrega)

- Botón «Pagar» en portal o wizard de alta.
- Cambio del webhook más allá de *consultar* este log cuando se cablee el `cod_trx`.
