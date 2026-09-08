# Spec: Botón de Pago Supervielle Cobranza Ágil (épica 4.1)

Contrato basado en **Cobranza Ágil Supervielle – API REST Botón de Pago v2.6**.
Canal: Cobrand + Banco Supervielle. SIRO no aplica.

## Scenario: configuración por ambiente

Given `Supervielle Settings`
When `sandbox_mode = 1`
Then `api_url` usa `https://cobranzaagiltst.supervielle.com.ar/rest/botonpago/publicacion`
And `rendicion_api_url` usa el host QA
And `secret_key` no tiene default versionado
And `url_ok`, `url_error`, `concepto_default`, `mode_of_payment` y `clearing_account` son obligatorios.

Given el modo y host no coinciden
When se intenta publicar
Then se rechaza antes del request HTTP.

## Scenario: payload v2.6 exacto

Given una `Sales Invoice` submitted, pendiente y vinculada a un `Socio`
When se publica el botón
Then se genera primero un `merchant_transaction_id` único de máximo 30 caracteres
And se envía como `DatoLibreEmp`
And el JSON sin `Hash` conserva este orden:

1. `IdEmpresa`
2. `UserName`
3. `Nombre`
4. `NroDoc`
5. `Concepto`
6. `Importe`
7. `DatoLibreEmp`
8. `URLOk`
9. `URLError`
10. `FechaVencPubl`
11. `ImporteSegVenc`
12. `FechaSegVencPubl`

And las fechas usan `ddMMyyyy`
And `Importe` usa punto y dos decimales
And `Concepto` no supera 10 caracteres
And `NroDoc` usa DNI del socio o, si no existe, su número de socio.

## Scenario: firma request y response

Given el payload ordenado
When se firma
Then `Hash` es SHA-256 de todos los valores enviados más `secret_key`, UTF-8.

Given HTTP 200 con `Token`, `AccessLink` y `Hash`
When se procesa la respuesta
Then se valida con comparación constante `SHA-256(Token + secret_key)`
And `AccessLink` debe ser HTTPS y pertenecer al host Supervielle del ambiente
And solo después se devuelve el link.

Given falta o no coincide el hash de respuesta
When se procesa
Then se registra el intento rechazado
And no se entrega token/link.

## Scenario: Payment Log de publicación

Given una publicación nueva
When se inicia el intento
Then se crea un `Payment Log` con `merchant_transaction_id = DatoLibreEmp`
And `gateway_transaction_id` queda vacío hasta recibir `IdPagoPortal`
And se vinculan Sales Invoice, Socio, importe y moneda
And el snapshot no contiene secret, Hash, Token ni AccessLink.

Given se reintenta la misma referencia local
When el servicio registra el intento
Then no crea otro log ni reasigna IDs a otra factura.

## Scenario: errores de red o negocio

Given error HTTP, de red o estructura de respuesta
When la publicación falla
Then el Payment Log queda `Rechazado`
And se registra un error sanitizado
And no se expone una excepción HTTP genérica al caller.

## Scenario: whitelist Desk fail-closed

Given Tesorería, Secretaría o System Manager con lectura sobre la factura
When llama `publicar_boton_pago_factura`
Then puede publicar.

Given Socio, Guest o un usuario sin lectura sobre la factura
When llama el endpoint
Then recibe `PermissionError`
And no hay request HTTP ni escritura bancaria.

## Fuera de alcance 4.1

- Callback de estados y rendiciones: épica 4.2.
- Producción sin aprobación explícita.
- Inventar `cod_trx`: v2.6 usa `IdPago` e `IdPagoPortal`.
