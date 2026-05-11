# Spec: Solicitud de Asociación pública (Sprint 1)

Given/When/Then para el **DocType `Solicitud de Asociación`** y su **Web Form público**.
Es la puerta de entrada del flujo prioritario:

`No Socio → Formulario público → Cola en dashboard Secretaría → Validación de
documentos → (OK) creación de User + Socio + email con botón de pago / (Rechazo)
email con motivos detallados`.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`
**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

**Ubicación del DocType:** `club_management/members/doctype/solicitud_asociacion/`
**Web Form:** `club_management/members/web_form/solicitud_asociacion/`
**Módulo Frappe:** `Members`

---

## Decisión de auth: flujo **híbrido**

- El formulario público se envía como **Guest** (sin cuenta previa).
- Al **validar** la solicitud, Secretaría dispara la creación atómica de:
  - `User` de portal (rol `Socio`),
  - `Socio` enlazado a ese `User` (estado `Pendiente de Pago`),
  - email con **stub local** de botón de pago (Sprint 1 no integra Supervielle real; se
    sustituye en Sprint 4).

Esto evita pedirle al solicitante crear una cuenta antes de saber si será aceptado,
y simplifica el anti-abuso al concentrar la creación de `User` en una acción autenticada.

---

## Campos propuestos del DocType `Solicitud de Asociación`

### Datos del solicitante

| Campo | Tipo | Reqd | Comentario |
|---|---|---|---|
| `nombre` | Data | sí | |
| `apellido` | Data | sí | |
| `dni` | Data | sí | Validación de formato (solo dígitos); será el `username` del futuro `User` |
| `nacionalidad` | Link → `Country` | **sí** | Default `"Argentina"` |
| `fecha_nacimiento` | Date | sí | El sistema deriva `es_menor` comparando con la fecha actual |
| `genero` | Select | **sí** | `Masculino` / `Femenino` / `Otro` / `Prefiero no decir` |
| `categoria_solicitada` | Select | sí | `Activo` / `Menor` / `Adherente` / `Jubilado` |
| `email` | Data (Email) | sí | **No único**: puede coincidir con el del tutor o de otro familiar socio |
| `telefono` | Data | sí | |
| `domicilio` | Small Text | sí | |
| `localidad` | Data | sí | |
| `provincia` | Data | sí | |
| `codigo_postal` | Data | sí | |

### Datos del tutor (solo si `categoria_solicitada = "Menor"`)

El tutor **no** tiene que ser Socio del club. El caso típico es un padre o madre
que asocia a sus hijos al club pero él/ella mismo/a no realiza actividad. Los
campos del tutor son los necesarios para crear o resolver un `Tutor No Socio` /
`Socio` al validar.

| Campo                 | Tipo             | Reqd               | Comentario                                                                                                                                                                                                                                                                                          |
| --------------------- | ---------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dni_tutor`           | Data             | sí (cuando menor)  | Si existe un `Socio` con este DNI, se reutiliza como tutor. Si no, se crea un `Tutor No Socio` con los datos siguientes                                                                                                                                                                              |
| `nombre_tutor`        | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `apellido_tutor`      | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `fecha_nacimiento_tutor` | Date          | sí (cuando menor)  | Debe corresponder a mayor de 18 años                                                                                                                                                                                                                                                               |
| `nacionalidad_tutor`  | Link → `Country` | sí (cuando menor)  | Default `"Argentina"`                                                                                                                                                                                                                                                                              |
| `genero_tutor`        | Select           | sí (cuando menor)  | `Masculino` / `Femenino` / `Otro` / `Prefiero no decir`                                                                                                                                                                                                                                            |
| `email_tutor`         | Data (Email)     | sí (cuando menor)  | Email de contacto del tutor; puede coincidir con `email` del menor                                                                                                                                                                                                                                  |
| `telefono_tutor`      | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `domicilio_tutor`     | Small Text       | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `localidad_tutor`     | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `provincia_tutor`     | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `codigo_postal_tutor` | Data             | sí (cuando menor)  |                                                                                                                                                                                                                                                                                                     |
| `rol_tutor`           | Select           | sí (cuando menor)  | `Padre` / `Madre` / `Tutor Legal` — se guarda como `rol` en `Miembro de Grupo Familiar` al validar al menor                                                                                                                                                                                        |

> Si el `dni_tutor` declarado ya corresponde a un `Socio` existente (con
> `categoria` ≠ `"Menor"` y mayor de 18 años), Secretaría valida la solicitud y el
> sistema reutiliza ese `Socio` como tutor. Si no existe, el sistema crea un
> `Tutor No Socio` con los datos declarados.

### Documentación adjunta

| Campo | Tipo | Reqd | Comentario |
|---|---|---|---|
| `dni_frente` | Attach | sí | imagen / PDF |
| `dni_dorso` | Attach | sí | imagen / PDF |
| `foto_perfil` | Attach Image | sí | |
| `ficha_medica` | Attach | **sí** | PDF / JPEG / PNG, ≤ 5MB; firmado por profesional médico |
| `comprobante_domicilio` | Attach | no | servicio, AFIP, etc. |

### Familia y preferencias (declarativas; no vinculantes)

| Campo | Tipo | Reqd | Comentario |
|---|---|---|---|
| `tiene_familiares_socios` | Check | no | Si sí, abre los siguientes |
| `familiares_existentes_dnis` | Small Text | no | DNIs separados por coma. Secretaría valida luego. |
| `actividad_interes` | Data | no | Texto libre o link a `Item`; declarativo |

### Workflow y trazabilidad

| Campo | Tipo | Reqd | Read-only | Comentario |
|---|---|---|---|---|
| `workflow_state` | Link → `Workflow State` | sí | sí | Inicial: `Pendiente` |
| `motivos_rechazo` | Text | depende | no | Requerido en transición a `Rechazada` |
| `observaciones_secretaria` | Text | no | no | Notas internas |
| `socio_generado` | Link → `Socio` | no | sí | Se setea al validar |
| `user_generado` | Link → `User` | no | sí | Vacío si el menor queda sin User propio (gestión vía tutor) |
| `grupo_familiar_generado` | Link → `Grupo Familiar` | no | sí | Grupo al que se incorporó el Socio al validar (nuevo o existente del tutor) |
| `token_seguimiento` | Data | no | sí | Token público para que el solicitante consulte estado |
| `enviado_desde_ip` | Data | no | sí | Para auditoría y rate-limit |

### Auditoría del flujo (todos `read-only`; setean server-side)

| Campo                          | Tipo          | Comentario                                              |
| ------------------------------ | ------------- | ------------------------------------------------------- |
| `validado_por`                 | Link → `User` | Quién ejecutó la transición `Validar`                   |
| `validado_en`                  | Datetime      | Timestamp                                               |
| `rechazado_por`                | Link → `User` | Quién ejecutó la transición `Rechazar`                  |
| `rechazado_en`                 | Datetime      | Timestamp                                               |
| `correccion_solicitada_por`    | Link → `User` | Última vez que se transicionó a `Requiere Corrección`   |
| `correccion_solicitada_en`     | Datetime      | Timestamp                                               |

> `owner` / `creation` ya capturan quién envió la Solicitud y cuándo (creación
> por Guest queda con `owner = "Guest"`). Los campos de arriba auditan
> específicamente cada transición del workflow.

**Naming:** `autoname` serie `SOL-.{YYYY}.-.####`.

**Workflow (DocType `Workflow` de Frappe):**

```
Pendiente            → estado inicial
   ↓ acción "Solicitar Corrección"  (Secretaria)
Requiere Corrección
   ↓ acción "Reenviar" (Secretaria o solicitante vía portal de seguimiento)
Pendiente
   ↓ acción "Validar"  (Secretaria)
Validada
   ↓ acción "Rechazar" (Secretaria)  desde Pendiente o Requiere Corrección
Rechazada            → estado terminal
```

---

## Permisos

| Rol | create | read | write | submit | cancel | delete |
|---|---|---|---|---|---|---|
| `Guest` | sí (solo vía Web Form) | no | no | no | no | no |
| `Secretaria` | sí | sí (todas) | sí | n/a | n/a | no |
| `System Manager` | sí | sí | sí | n/a | n/a | sí |
| `Socio` | no | no | no | no | no | no |

`Guest` no debe poder leer ninguna `Solicitud de Asociación` por `/api/resource/`.
Solo crea vía endpoint del Web Form.

---

## Scenario: alta pública desde Web Form como Guest

Given un visitante anónimo sin sesión Frappe
And el Web Form `solicitud-asociacion` está publicado y aceptando submissions
When envía el form con todos los campos requeridos + adjuntos válidos
Then se crea un documento `Solicitud de Asociación` con `workflow_state = "Pendiente"`
And se genera `token_seguimiento` (UUID v4 o token firmado del request)
And se persiste `enviado_desde_ip` desde la request
And el endpoint responde 200 OK con un mensaje de confirmación que **no expone** el `name`
del documento (solo el `token_seguimiento`)
And se envía un email al solicitante confirmando la recepción.

---

## Scenario: campos obligatorios faltantes bloquean el alta

Given un visitante anónimo
When envía el Web Form **sin** `dni_frente` (o cualquier campo `reqd: 1`)
Then el envío falla con `frappe.ValidationError`
And no se crea ningún documento
And el visitante recibe un mensaje de error indicando qué campo falta
(sin filtrar nombres internos de campos a un usuario hostil).

---

## Scenario: `ficha_medica` valida MIME y tamaño en el Web Form

Given un visitante anónimo completando el Web Form
When adjunta como `ficha_medica` un archivo cuyo MIME **no** es
`application/pdf`, `image/jpeg` ni `image/png`
Then el envío falla con `frappe.ValidationError("Tipo de archivo no permitido")`
And no se crea ningún documento.

Given el mismo visitante
When adjunta como `ficha_medica` un archivo con MIME válido pero tamaño > 5 MB
Then el envío falla con `frappe.ValidationError("Archivo excede 5 MB")`
And no se crea ningún documento.

(Reutiliza el helper validador del controlador `Socio`; mismo criterio aquí y en
Desk.)

---

## Scenario: `Guest` no puede leer ninguna solicitud existente

Given existe al menos una `Solicitud de Asociación` con `name` = "SOL-2026-0001"
And el cliente no tiene sesión Frappe (es Guest)
When intenta `GET /api/resource/Solicitud de Asociación` o `GET /api/resource/Solicitud de Asociación/SOL-2026-0001`
Then la respuesta es `403 Forbidden` o `404 Not Found`
And no se filtran datos personales del solicitante.

---

## Scenario: rate-limit por IP

Given una IP X envía 5 solicitudes en menos de 10 minutos
When intenta enviar la sexta dentro de esa ventana
Then la sexta es rechazada con `frappe.RateLimitExceededError` o HTTP 429
And no se crea documento
And se registra el intento en `frappe.log_error` (sin volcar PII en el log).

(Umbral inicial: 5/10min por IP. Ajustable en `Club Settings` futuro.)

---

## Scenario: el solicitante consulta el estado con su `token_seguimiento`

Given una `Solicitud de Asociación` con `token_seguimiento = "tk-…"` y `workflow_state = "Pendiente"`
And un endpoint público `consultar_solicitud(token)` whitelist `allow_guest=True`
When el solicitante consulta con su `token`
Then recibe un payload con `workflow_state`, fecha de creación, y (si aplica) `motivos_rechazo`
And **no** recibe documentos adjuntos ni datos de otros solicitantes
And un `token` inválido o vencido responde `404` sin distinguir entre "no existe" y "no autorizado".

---

## Scenario: Secretaría ve la cola de pendientes

Given existen `Solicitud de Asociación` con `workflow_state` en `{Pendiente, Requiere Corrección, Validada, Rechazada}`
And un usuario con rol `Secretaria`
When abre la List View `Solicitud de Asociación` con el filtro por defecto del workspace
Then ve solo las solicitudes con `workflow_state = "Pendiente"`
And puede cambiar el filtro para ver `Requiere Corrección`, `Validada` o `Rechazada`
And ordena por fecha de creación descendente por defecto.

(El workspace y los shortcuts se cubren en Sprint 2; este scenario testea solo
filtros por defecto del listado.)

---

## Scenario: validar adulto crea atómicamente `User` + `Socio` + nuevo `Grupo Familiar`

Given una `Solicitud de Asociación` con `workflow_state = "Pendiente"`,
`categoria_solicitada` ∈ `{"Activo", "Adherente", "Jubilado"}` y datos completos
And no existe un `User` con `name` = `<email del solicitante>`
And no existe un `User` con `username` = `<dni del solicitante>`
And no existe un `Socio` con ese DNI
When `Secretaria` ejecuta la acción `Validar` (transición de workflow)
Then en una sola transacción:
  - se crea un `User` con `name = <email>`, `username = <dni>`,
    `enabled = 1`, `user_type = "Website User"`, rol `Socio`,
  - se crea un `Socio` con `estado = "Pendiente de Pago"`, `dni`, `email`,
    `nacionalidad`, `categoria = <categoria_solicitada>`,
    `user = <name del User>`, `solicitud_origen = <name de la solicitud>`,
    `alta_validada_por = frappe.session.user`,
    `alta_validada_en = frappe.utils.now()`,
  - se crea un `Grupo Familiar` nuevo con `titulares` = una sola fila
    `{tipo_titular: "Socio", titular: <Socio>, es_principal: 1, rol: "Titular"}`,
  - el `Socio` queda automáticamente en `miembros` con `rol = "Titular"` (por la
    sincronización del controlador de `Grupo Familiar`),
  - el `Socio` queda con `grupo_familiar = <nuevo grupo>`,
  - los adjuntos `dni_frente`, `dni_dorso`, `foto_perfil`, `ficha_medica` se
    referencian (o copian) en el `Socio`,
  - la solicitud queda con `workflow_state = "Validada"`, `socio_generado`,
    `user_generado`, `grupo_familiar_generado` poblados, `validado_por` y
    `validado_en` registrados,
  - se encola un email al solicitante con el **link stub** de pago de primera cuota.
And si **cualquier paso** falla, la transacción se aborta (no queda `User` huérfano
sin `Socio`, ni grupo huérfano sin titulares, ni viceversa).

---

## Scenario: validar adulto con email ya tomado bloquea

Given una `Solicitud de Asociación` con `categoria_solicitada` ≠ `"Menor"`,
`email` = "familia@example.com"
And ya existe un `User` con `name` = "familia@example.com"
When `Secretaria` ejecuta la acción `Validar`
Then la transición falla con `frappe.ValidationError`
(mensaje: "El email ya tiene cuenta en el portal; pedí al solicitante un email distinto")
And no se crea `User`, ni `Socio`, ni `Grupo Familiar`
And la solicitud permanece en `workflow_state = "Pendiente"`
And Secretaría puede usar la transición `Solicitar Corrección` para que el
solicitante reenvíe con email propio.

---

## Scenario: validar menor con tutor que ya es `Socio` — sin crear `User` para el menor

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "familia@example.com"`,
`dni_tutor = "20111111"`, `rol_tutor = "Padre"`
And ya existe un `Socio` `S_tutor` con `dni = "20111111"`, mayor de edad,
titular activo (`es_principal = 1`) de `Grupo Familiar` `G` (vía una fila
`{tipo_titular: "Socio", titular: S_tutor}` en `G.titulares`)
And ya existe un `User` con `name = "familia@example.com"` (del tutor)
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - **no** se crea `User` para el menor (no hay email técnico),
  - se crea un `Socio` con `dni = "55222222"`, `categoria = "Menor"`,
    `email = "familia@example.com"`, `user = ""` (vacío),
    `tipo_tutor = "Socio"`, `tutor = <S_tutor.name>`,
    `grupo_familiar = G`,
    `estado = "Pendiente de Pago"`, `solicitud_origen = <name>`,
    auditoría poblada,
  - se agrega una nueva fila a `G.miembros` con `socio = <Socio menor>`,
    `rol = "Hijo"` (derivado de `rol_tutor = "Padre"`), `desde = hoy`,
  - la solicitud queda `Validada`, `socio_generado` poblado, `user_generado` vacío,
    `grupo_familiar_generado = G`,
  - el email del stub de pago se envía a `"familia@example.com"` (el tutor recibe
    el link para pagar la primera cuota del menor).

---

## Scenario: validar menor con tutor **no Socio** — crea `Tutor No Socio` y `Grupo Familiar`

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "familia@example.com"`,
`dni_tutor = "20111111"`, `nombre_tutor = "Juan"`, `apellido_tutor = "Pérez"`,
`email_tutor = "papa@example.com"`, `rol_tutor = "Padre"` (más demás datos de
contacto y `fecha_nacimiento_tutor` mayor de 18)
And **no** existe ningún `Socio` con `dni = "20111111"`
And **no** existe ningún `Tutor No Socio` con `dni = "20111111"`
And no existe `User` con `name = "papa@example.com"` ni `username = "20111111"`
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - se crea un `Tutor No Socio` `T_padre` con todos los datos declarados del tutor,
  - se provisiona un `User` para `T_padre` con `name = "papa@example.com"`,
    `username = "20111111"` (el tutor podrá pagar y gestionar desde el portal),
  - se crea un `Grupo Familiar` `G` con `titulares` = una sola fila
    `{tipo_titular: "Tutor No Socio", titular: T_padre, es_principal: 1, rol: <rol_tutor>}`,
  - se crea un `Socio` `S_menor` con `dni = "55222222"`, `categoria = "Menor"`,
    `email = "familia@example.com"`, `user = ""` (vacío),
    `tipo_tutor = "Tutor No Socio"`, `tutor = T_padre`,
    `grupo_familiar = G`, `estado = "Pendiente de Pago"`,
    `solicitud_origen = <name>`, auditoría poblada,
  - se agrega una fila a `G.miembros` con `socio = S_menor`, `rol = "Hijo"`,
    `desde = hoy`,
  - la solicitud queda `Validada`, `socio_generado = S_menor`,
    `user_generado = ""`, `grupo_familiar_generado = G`,
  - el email del stub de pago se envía a `papa@example.com` (el tutor recibe el
    link para pagar la primera cuota del menor).
And si **cualquier paso** falla, la transacción se aborta (no queda
`Tutor No Socio` huérfano sin grupo, ni grupo sin titulares, etc.).

> **Nota sobre cotitulares (padre + madre):** la Solicitud carga **un** tutor.
> Si ambos padres son adultos responsables del grupo, Secretaría agrega al
> segundo como cotitular (`es_principal = 0`) editando el `Grupo Familiar`
> después de validar al primer menor. No se carga directamente desde el Web Form
> público en Sprint 1.

---

## Scenario: validar segundo menor del mismo tutor **no Socio** — reutiliza tutor y grupo

Given un `Tutor No Socio` `T_padre` ya creado (por una solicitud previa de su
primer hijo `S_hijo1`), titular de `Grupo Familiar` `G` que ya contiene a
`S_hijo1`
And una nueva `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni_tutor = T_padre.dni` (el mismo padre), datos consistentes
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - **no** se crea un nuevo `Tutor No Socio` (se reutiliza `T_padre`),
  - **no** se crea un nuevo `Grupo Familiar` (se reutiliza `G`),
  - se crea un `Socio` `S_hijo2` con `tipo_tutor = "Tutor No Socio"`,
    `tutor = T_padre`, `grupo_familiar = G`,
  - se agrega `S_hijo2` a `G.miembros`,
  - la solicitud queda `Validada` con `grupo_familiar_generado = G`.

> En esta iteración no se aplica todavía el descuento por hermanos
> (out of scope Sprint 0/1; cubierto por `socios_categoria_validacion.md`).
> La presencia de varios menores en el mismo grupo es prerrequisito de ese
> beneficio futuro.

---

## Scenario: validar menor con datos de tutor incompletos bloquea

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`
And **no** existe `Socio` ni `Tutor No Socio` con `dni_tutor` declarado
And **falta** alguno de los campos obligatorios del bloque "Datos del tutor"
(p. ej. `email_tutor` vacío)
When `Secretaria` ejecuta `Validar`
Then la transición falla con `frappe.ValidationError`
(mensaje: "Datos del tutor incompletos: `email_tutor` es obligatorio")
And nada se persiste y la solicitud permanece en `Pendiente`
(Secretaría puede pasarla a `Requiere Corrección` para que el solicitante
complete los datos del tutor).

---

## Scenario: validar menor con tutor menor de edad bloquea

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"` y
datos de tutor cuyo `fecha_nacimiento_tutor` lo deja en (hoy − 16 años)
(o un `Socio`/`Tutor No Socio` existente con esos datos)
When `Secretaria` ejecuta `Validar`
Then la transición falla con `frappe.ValidationError`
(mensaje: "Tutor debe ser mayor de 18 años")
And nada se persiste y la solicitud permanece en `Pendiente`.

---

## Scenario: validar es idempotente si se vuelve a ejecutar

Given una `Solicitud de Asociación` ya `Validada` con `socio_generado` poblado
(`user_generado` puede estar vacío si era menor con tutor)
When `Secretaria` ejecuta `Validar` nuevamente (intencional o accidentalmente)
Then no se crean nuevos `User`, `Socio` ni `Grupo Familiar`
And la solicitud sigue `Validada` con los mismos enlaces
And `validado_por` / `validado_en` mantienen el valor de la primera validación
(no se sobreescriben)
And no se reenvía el email automáticamente (debe haber acción explícita "Reenviar email").

---

## Scenario: validación con DNI ya asociado bloquea

Given una `Solicitud de Asociación` con `dni` = "30123456"
And ya existe un `Socio` con ese `dni`
When `Secretaria` intenta `Validar` la solicitud
Then la transición falla con `frappe.ValidationError` ("DNI ya registrado como Socio")
And la solicitud permanece en `Pendiente` (no pasa a `Validada`)
And Secretaría puede pasarla a `Rechazada` con motivo "DNI duplicado".

---

## Scenario: rechazar requiere `motivos_rechazo`

Given una `Solicitud de Asociación` con `workflow_state = "Pendiente"`
And `motivos_rechazo` vacío
When `Secretaria` intenta la transición `Rechazar`
Then la transición falla con `frappe.ValidationError` ("motivos_rechazo es obligatorio")
And el `workflow_state` permanece en `Pendiente`.

Given la misma solicitud
And ahora `motivos_rechazo` contiene texto
When `Secretaria` ejecuta `Rechazar`
Then `workflow_state` pasa a `Rechazada`
And se encola un email al solicitante con el contenido de `motivos_rechazo`,
**escapado** según las reglas de XSS de `.cursor/rules/security.mdc`
(`frappe.utils.escape_html` o `| e` en Jinja).

---

## Scenario: Solicitar Corrección permite reenvío sin perder adjuntos previos

Given una `Solicitud de Asociación` con `workflow_state = "Pendiente"`
When `Secretaria` ejecuta `Solicitar Corrección` con notas en `observaciones_secretaria`
Then `workflow_state` pasa a `Requiere Corrección`
And se envía email al solicitante con el `token_seguimiento` y las observaciones
And el solicitante puede actualizar adjuntos/datos vía un endpoint público autenticado por token
(scope: solo la misma solicitud)
And al reenviar, `workflow_state` vuelve a `Pendiente`
And los adjuntos anteriores no se pierden silenciosamente (quedan en el historial / versiones).

---

## Scenario: stub del botón de pago (Sprint 1, sustituido en Sprint 4)

Given una `Solicitud de Asociación` recién `Validada`
And la integración Supervielle real **no** está activa en Sprint 1
When el sistema envía el email post-validación
Then el link del email apunta a un endpoint **stub** del propio sitio
(`/api/method/club_management.members.api.pago_stub` o `/pago-stub/<token>`)
And ese endpoint responde una página simple con "Pago simulado: marcar como pagado"
And al confirmar, dispara la misma lógica que el webhook real
(crear `Payment Entry` ficticio o simplemente cambiar `Socio.estado` a `Activo`).
And queda documentado en el código que esta ruta es **temporal** y se reemplaza
en Sprint 4 por `SupervielleAPI.generar_boton_pago` + webhook real ya existente.

---

## Scenario: email de validación referencia solo datos del propio solicitante

Given una `Solicitud de Asociación` validada para `ana@example.com`
When se renderiza el template del email post-validación
Then el cuerpo del email contiene solo datos de `ana`
And no expone PII (DNI, dirección) en el cuerpo del email (basta nombre + monto + link)
And el link de pago lleva un token único que **no es** adivinable por enumeración.

---

## Scenario: email de rechazo escapa HTML en `motivos_rechazo`

Given una `Solicitud de Asociación` rechazada con
`motivos_rechazo = '<script>alert(1)</script> Falta DNI dorso'`
When se renderiza el template del email de rechazo
Then el contenido renderizado contiene el texto literal escapado
(`&lt;script&gt;alert(1)&lt;/script&gt; Falta DNI dorso`)
And el cliente de correo no ejecuta script alguno
And esto se cubre con un test sobre la función de render del email.

---

## Notas de implementación (no testeables aquí)

- DocType: `members/doctype/solicitud_asociacion/solicitud_asociacion.{json,py,js}`.
- Web Form: `members/web_form/solicitud_asociacion/solicitud_asociacion.{json,html?}`.
- API del flujo de validación: `members/api.py` con `validar_solicitud(name)`,
  `rechazar_solicitud(name)`, `solicitar_correccion(name)`, `consultar_solicitud(token)`,
  `pago_stub(token)`. Toda mutación de workflow corre dentro de `frappe.db.savepoint`
  o transacción explícita para garantizar atomicidad de `User` + `Socio` +
  `Grupo Familiar` + adjuntos + email.
- Workflow JSON: `members/workflow/solicitud_asociacion/solicitud_asociacion.json`.
- Email Templates: `members/email_template/` con `solicitud_validada.html`,
  `solicitud_rechazada.html`, `solicitud_requiere_correccion.html`. El enlace al
  stub de pago se inserta vía Jinja con `token` firmado/expirado.
- `validar_solicitud` reutiliza:
  - `members/services/user_provisioning.py::provision_user_for_socio(socio_doc)` —
    crea `User` si y solo si el email no está tomado; **nunca** genera email técnico;
    devuelve `None` si el menor queda sin User.
  - `members/services/grupo_familiar.py::ensure_grupo_for_socio(socio_doc, tutor_doc=None)` —
    crea `Grupo Familiar` nuevo si el solicitante es adulto, o agrega al menor al
    `Grupo Familiar` del tutor existente.
- Auditoría:
  - `before_save` del DocType setea `validado_por/en`, `rechazado_por/en`,
    `correccion_solicitada_por/en` según la transición de `workflow_state`.
  - Si `workflow_state` no cambia, los campos de auditoría se mantienen
    (no se sobreescriben en saves "intrascendentes").
- Tests:
  - `members/doctype/solicitud_asociacion/test_solicitud_asociacion.py`
    → alta Guest, validaciones de campos, rate-limit, validación MIME de ficha médica.
  - `members/doctype/solicitud_asociacion/test_workflow_solicitud_asociacion.py`
    → transiciones (validar adulto / validar menor con tutor / rechazar / corrección),
    idempotencia, auditoría de timestamps.
  - `tests/test_solicitud_asociacion_isolation.py`
    → Guest no lee, Socio no lee, Secretaría sí.
  - `tests/test_solicitud_asociacion_emails.py`
    → escape XSS en `motivos_rechazo`, contenido del email validada.

- En `hooks.py` (al implementar):
  - `has_website_permission` / `permission_query_conditions` para
    `Solicitud de Asociación` si se permite portal de seguimiento.
  - No exponer la solicitud por `/api/resource/` a Guest.
