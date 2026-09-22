# Spec: conciliación y rendiciones Supervielle (épica 4.2)

Contratos: callback Botón de Pago v2.6 y rendiciones API general v6.2.
Son productos distintos y la rendición queda en preview hasta confirmar su habilitación
y el orden de firma de la respuesta anidada.

## Scenario: autenticación antes de cualquier efecto

Given un callback JSON de Cobranza Ágil
When falta el `Hash`, no coincide o el esquema excede el contrato
Then responde 403
And no consulta ni modifica Sales Invoice, Payment Log o Payment Entry.

Given un callback válido
When se autentica
Then usa SHA-256 de los valores en el orden contractual, excluye `Hash`,
anexa `secret_key` y compara con `hmac.compare_digest`.

## Scenario: identidad local y bancaria

Given `IdPago` recibido
When se procesa
Then resuelve exactamente un Payment Log por `merchant_transaction_id`
And `IdPagoPortal` se asigna una sola vez como `gateway_transaction_id`
And el mismo ID bancario no puede asociarse a otra factura.

## Scenario: estados y Payment Entry

Given un callback autenticado con estado `3` Pagado
When se procesa
Then guarda un `Payment Gateway Event`
And no crea Payment Entry.

Given un callback autenticado con estado `5` Validado
And el importe ARS coincide exactamente con el saldo esperado
When se procesa
Then crea y submite un único Payment Entry con `Cobros Plus (ARS)`
And lo vincula al Payment Log
And marca el log `Conciliado`.

Given el mismo evento se reintenta
When se procesa otra vez
Then responde 200
And no duplica el evento ni el Payment Entry.

Given estado rechazado o reversado
When se procesa
Then registra el evento
And no crea ni cancela automáticamente asientos
And deja revisión manual para Tesorería.

Given falla la creación o submit del Payment Entry
When termina la request
Then no marca el Payment Log conciliado
And responde error temporal para que el banco reintente.

## Scenario: archivo de eventos inmutable

Given cada transición autenticada
When se persiste
Then `Payment Gateway Event` conserva proveedor, IDs, estado, fecha, payload sanitizado
y resultado
And su clave idempotente combina proveedor, IdPagoPortal, estado y fecha de cambio.

## Scenario: consulta de rendiciones

Given System Manager/Tesorería solicita preview de `/rest/rendicion`
When arma el request
Then firma los filtros v6.2 en orden y usa el host del ambiente configurado
And parsea `idRendicion`, `Documentos`, `Instrumentos`, retenciones y disputas.

Given `Documentos[].Libre1` coincide con `merchant_transaction_id`
And un instrumento tiene estado `AC`
When la firma de respuesta todavía no puede validarse inequívocamente
Then informa el candidato en preview
And no crea Payment Entry.

Given Cobrand provee un vector de firma válido para la respuesta anidada
When se habilite `rendicion_apply_enabled`
Then `AC` puede reutilizar el servicio de conciliación como fallback idempotente.

Given `RC`, `RD` o `ES`
When se procesa la rendición
Then nunca crea Payment Entry.

## Scenario: tick de scheduler y polling

Given `Supervielle Settings.sandbox_mode = 1` **o** `polling_enabled = 1`
When corre el job `process_renditions_scheduler_tick`
Then consulta el lote de rendiciones en el host configurado
And procesa cada respuesta del lote sin aplicar Payment Entry automáticamente
mientras `rendicion_apply_enabled` esté desactivado.

Given `sandbox_mode = 0` **y** `polling_enabled = 0`
When corre el mismo job
Then no llama a la API de rendiciones
And retorna un resultado vacío / `skipped`.

## Scenario: verificación de hash anidado (vector provisional)

El banco aún no confirmó el vector oficial de firma de la respuesta anidada v6.2.
Hasta entonces se usa un hash provisional: SHA-256 de los valores escalares en
recorrido DFS (dict/list), excluyendo claves `Hash`/`hash`, más `secret_key`.

Given una respuesta de rendiciones con `Hash` ausente o distinto al provisional
And `sandbox_mode = 1` (modo auditoría, `strict=False`)
When el verificador independiente evalúa el payload
Then no lanza error ni interrumpe el tick del scheduler
And registra un `Payment Gateway Event` con `processing_result` /
`status_description` = `Error de Verificación`
And emite una advertencia estructurada en el logger (`rendition_hash_mismatch`)
And el payload persistido omite `Hash` / secretos
And `hash_verified` queda en falso
And el parseo preview del resto del lote continúa.

Given la misma discrepancia de hash
And `sandbox_mode = 0` (producción, `strict=True`)
When el verificador evalúa el payload
Then lanza `SupervielleIntegrationError`
And no crea Payment Entry ni aplica conciliación.

Given un payload anidado cuyo `Hash` coincide con el provisional
When se verifica en cualquier modo
Then `hash_verified` es verdadero
And no se registra evento de error de verificación.

## Scenario: persistencia cruda e idempotencia de red

Given una respuesta de rendición procesada por el tick
When se persiste el evento
Then `Payment Gateway Event` guarda el payload crudo sanitizado (sin `Hash`)
And la clave idempotente combina proveedor, identidad de rendición/instrumento
(o firma de contenido) y resultado.

Given el mismo lote se reintenta por timeout/red
When se procesa otra vez con la misma identidad
Then no duplica el `Payment Gateway Event`
And reutiliza el `event_key` existente.

## Permisos y datos

- El callback puede ser guest únicamente con la firma como gate explícito.
- Socio no puede leer Payment Log ni Payment Gateway Event.
- Tesorería tiene lectura; la mutación se realiza solo por servicios internos.
- No se loguean secret, Hash, Token ni AccessLink.
- No se ejecuta `frappe.db.commit()` manual.
