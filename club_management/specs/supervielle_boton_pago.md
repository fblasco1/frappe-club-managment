# Spec: Botón de Pago Supervielle Cobranza Ágil / Cobrand (épica 4.1)

Given/When/Then para publicación de deuda vía API REST de Cobranza Ágil
(Botón de Pago) y persistencia en `Payment Log`.

**Canal:** Cobrand + Banco Supervielle. **SIRO no aplica.**

**Ruta en Bench:** `apps/club_management/club_management/specs/`

**Código:** `club_management.integrations.supervielle.client`  
**Configuración:** DocType Single `Supervielle Settings` (módulo Finance).  
**Trazabilidad:** DocType existente `Payment Log` (no se crea un log paralelo).

**Endpoint sandbox (doc banco, 2026-09-07):**

`https://cobranzaagiltst.supervielle.com.ar/rest/botonpago/publicacion`

La firma SHA-256 es la ya especificada en `supervielle_cobros_plus_api.md`
(concatenar valores JSON en orden, excluir `hash`/`Hash`, anexar `secret_key`).

---

## Scenario: Supervielle Settings sandbox por defecto

Given el Single `Supervielle Settings` recién migrado
When un System Manager abre el formulario
Then `sandbox_mode` está marcado (default 1)
And `cuit_emisor` es `20406381928`
And `api_url` es la URL sandbox de publicación
And `concepto_default` es `PRUEBA`
And `secret_key` es Password (sin valor por defecto en el JSON del DocType)

---

## Scenario: payload de checkout a partir de una Sales Invoice

Given una `Sales Invoice` submitted de cuota/arancel con `outstanding_amount` > 0
And un `Socio` vinculado (campo `socio` / `custom_socio`)
And `Supervielle Settings` con `concepto_default`, `cuit_emisor` y `secret_key`
When el cliente arma el payload de publicación
Then el JSON (sin `Hash`) contiene, **en este orden de claves**:

| Clave | Origen |
|-------|--------|
| `Cuit` | `cuit_emisor` (solo dígitos) |
| `Concepto` | `concepto_default` |
| `IdCliente` | `Socio.numero_socio` (string) |
| `IdReferencia` | `Sales Invoice.name` |
| `Importe` | `outstanding_amount` con 2 decimales (`"19500.00"`) |
| `Moneda` | `ARS` |
| `FechaVencimiento` | `due_date` ISO `YYYY-MM-DD` |
| `Email` | `Socio.email` |
| `Nombre` | nombre visible del socio |

And el CUIT no incluye guiones
And no se incluye la `secret_key` en el JSON

---

## Scenario: firma SHA-256 inyectada antes del POST

Given el payload base del escenario anterior
When el cliente prepara la request
Then calcula SHA-256 hex minúsculas concatenando los valores en orden,
excluyendo cualquier clave `hash`/`Hash`, y anexando la `secret_key`
And el payload final incluye `"Hash"` con ese valor
And el POST va a `api_url` (URL completa, sin concatenar otro path)

---

## Scenario: sandbox_mode impide publicar contra producción

Given `sandbox_mode = 1`
And `api_url` apunta a un host que no es `cobranzaagiltst.supervielle.com.ar`
When se intenta publicar
Then se lanza `SupervielleIntegrationError`
And no se envía HTTP
And no se crea Payment Log de éxito

Given `sandbox_mode = 0`
And `api_url` apunta al host de test (`cobranzaagiltst`)
When se intenta publicar
Then se lanza `SupervielleIntegrationError` (clave/ambiente cruzados)

---

## Scenario: respuesta exitosa devuelve URL o identificador

Given el banco responde HTTP 200 con JSON que incluye URL de botón
  (`UrlBotonPago` / `Url` / `urlPago` / equivalentes)
When el cliente procesa la respuesta
Then devuelve esa URL para redirección del socio
And el identificador de transacción del banco (si viene) se usa como
`Payment Log.gateway_transaction_id`

Given HTTP 200 con identificador y **sin** URL
When el cliente procesa la respuesta
Then igual considera éxito y expone el identificador
And no inventa una URL

---

## Scenario: error HTTP o de negocio se registra y no rompe el caller con 500 genérico

Given el banco responde HTTP distinto de 200
Or HTTP 200 con código/mensaje de error de negocio
When el cliente publica
Then se registra `frappe.log_error` con título `Supervielle API Error`
And se lanza `SupervielleIntegrationError`
And queda un `Payment Log` en estado `Rechazado` con snapshot de request/response
And el snapshot **no** contiene la `secret_key`

---

## Scenario: Payment Log por cada intento (idempotencia del ID bancario)

Given una publicación exitosa con `IdTransaccion` (o equivalente) = `X`
When el servicio registra el evento
Then existe un Payment Log `provider = Banco Supervielle`, `status = Recibido`
And `gateway_reference` es el name de la Sales Invoice
And `payload_json` guarda `{request, response, http_status}`
And `sales_invoice` y `socio` quedan vinculados
And `gateway_transaction_id` es inmutable (reglas de `payment_log.md`)

Given un segundo intento con el mismo ID `X` y la misma factura
When se registra
Then no se inserta un segundo Payment Log (idempotencia)

---

## Scenario: factura pagada o sin socio no se publica

Given `outstanding_amount = 0`
When se solicita el botón
Then `ValidationError` y no hay POST

Given la factura no tiene Socio vinculado
When se solicita el botón
Then `ValidationError` y no hay POST

---

## Scenario: whitelist Desk con permiso (no guest)

Given un usuario con rol `Tesoreria`, `Secretaria` o `System Manager`
And permiso de lectura sobre la `Sales Invoice`
When llama `publicar_boton_pago_factura`
Then se publica (o se propaga el error tipado del banco)

Given un usuario con rol `Socio`
When llama el mismo método
Then `PermissionError`
And no se envía HTTP

Given `allow_guest` no está habilitado
When un invitado llama el método
Then Frappe exige sesión (fail closed)

---

## Credenciales sandbox (no commitear en defaults de Password)

| Campo | Valor de test |
|-------|----------------|
| `secret_key` | GUID de sandbox provisto por el banco (cargar en Desk / test fixture) |
| `cuit_emisor` | `20406381928` |
| `concepto_default` | `PRUEBA` |

La `secret_key` de sandbox se setea en tests vía fixture y en Desk a mano.
No va como default del JSON del DocType.

---

## Fuera de alcance (esta entrega)

- Webhook de cobro (épica 4.2; spec `supervielle_cobros_plus_webhook.md`).
- Botón «Pagar» en portal socio.
- Corte a producción (`sandbox_mode = 0`) sin OK explícito del PO.
- Inventar campos extra no listados aquí.
