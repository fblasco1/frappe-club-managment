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

## Decisión sobre el `name` técnico del DocType

El `name` técnico del DocType es **`Solicitud Asociacion`** (ASCII puro,
sin tilde y sin "de"). Esto es por dos motivos:

1. Frappe deriva el path del módulo Python con `frappe.scrub(name)`, que no
   normaliza tildes ni mayúsculas. `scrub("Solicitud de Asociación") =
   "solicitud_de_asociación"`, lo que forzaría un folder con tilde en el
   filesystem (frágil entre Windows / Linux / Git).
2. El name interno se mantiene ASCII puro para evitar problemas de encoding
   entre sistemas, BD, URLs y serializaciones.

El **concepto de negocio** sigue siendo "Solicitud de Asociación". El
**label visible** en Desk se va a traducir a "Solicitud de Asociación" vía
`<app>/translations/es.csv` cuando se haga el sprint de i18n. Mientras
tanto, Desk muestra el `name` técnico.

Esta decisión se refleja en:
- Folder físico: `members/doctype/solicitud_asociacion/`
- Clase Python: `SolicitudAsociacion`
- Slug del módulo: `solicitud_asociacion`
- Tabla DB: `tabSolicitud Asociacion`
- API REST: `/api/resource/Solicitud Asociacion/<name>`

En el resto del documento "Solicitud de Asociación" se sigue usando como
nombre conceptual (más legible), pero técnicamente refiere al DocType
`Solicitud Asociacion`.

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

## Decisión sobre `User` para menores

Política unificada al validar un menor:

1. Si `solicitud.email == solicitud.email_tutor` (mismo email para menor y tutor),
   **no** se crea `User` para el menor. El menor se gestiona vía el `User` del
   tutor. `Socio.user` queda vacío.
2. Si `solicitud.email != solicitud.email_tutor` y `solicitud.email` **no** está
   tomado por otro `User`, se crea un `User` propio para el menor con `name =
   solicitud.email`, `username = solicitud.dni`, rol `Socio`. `Socio.user` queda
   poblado.
3. Si `solicitud.email != solicitud.email_tutor` pero `solicitud.email` **ya
   está tomado** por otro `User`, la transición `Validar` falla con
   `frappe.ValidationError` y el solicitante debe usar otro email para el menor
   (o compartir el del tutor).

Esta política es opt-out: por defecto se crea `User` si los datos lo permiten.
Aun cuando el menor tenga `User` propio, el **email de pago** se envía al
`email_tutor` porque el tutor es el responsable financiero.

---

## Decisión sobre auditoría de validación

La auditoría de la transición (`validado_por`, `validado_en`, `rechazado_por`,
`rechazado_en`, `correccion_solicitada_por`, `correccion_solicitada_en`) vive
**exclusivamente** en la `Solicitud de Asociación`.

El `Socio` generado **no** duplica esos campos. La trazabilidad se obtiene vía
`Socio.solicitud_origen` → `Solicitud.validado_por` / `Solicitud.validado_en`.

Esto evita duplicación y mantener dos puntos sincronizados.

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

> **Identificación de IP detrás de proxy:** en producción el bench corre detrás
> de nginx, por lo que `frappe.local.request.remote_addr` devuelve la IP del
> proxy. La función de identificación de cliente debe preferir el primer valor
> del header `X-Forwarded-For` (si está presente y el proxy es confiable) y caer
> a `remote_addr` si no. La IP resuelta se persiste en `enviado_desde_ip` y se
> usa como clave del rate-limit. Esto se cubre con un test que mockea
> `frappe.local.request.headers` con `X-Forwarded-For` y verifica que la IP
> usada en `enviado_desde_ip` sea la del cliente, no la del proxy.

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
    (la auditoría de la validación queda en la propia Solicitud,
    cf. sección "Decisión sobre auditoría de validación"),
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

## Scenario: validar adulto con `familiares_existentes_dnis` NO une grupos automáticamente

Given una `Solicitud de Asociación` con `categoria_solicitada = "Activo"`,
`tiene_familiares_socios = 1`, `familiares_existentes_dnis = "20111111,30222222"`
And ya existen `Socio`s con esos DNIs, titulares activos de un `Grupo Familiar`
preexistente `G_familia`
When `Secretaria` ejecuta `Validar`
Then se crea un `Grupo Familiar` **nuevo** `G_nuevo` para el solicitante
(no se reutiliza `G_familia`)
And el solicitante queda como único titular principal de `G_nuevo`
And el campo `familiares_existentes_dnis` queda persistido en la `Solicitud`
para revisión posterior
And la `Solicitud.observaciones_secretaria` puede ser actualizada por Secretaría
para registrar la decisión de unión manual posterior.

> En Sprint 1, `familiares_existentes_dnis` es **puramente declarativo**: el
> sistema lo persiste pero no actúa sobre él. Secretaría decide manualmente, vía
> Desk, si agrega al nuevo Socio como cotitular del grupo existente o mantiene
> el grupo nuevo. La unión automática queda fuera de scope.

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

## Scenario: validar menor con tutor que ya es `Socio` — email compartido, sin `User` para el menor

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "familia@example.com"`,
`dni_tutor = "20111111"`, `email_tutor = "familia@example.com"` (mismo email),
`rol_tutor = "Padre"`
And ya existe un `Socio` `S_tutor` con `dni = "20111111"`, mayor de edad,
titular activo (`es_principal = 1`) de `Grupo Familiar` `G` (vía una fila
`{tipo_titular: "Socio", titular: S_tutor}` en `G.titulares`)
And ya existe un `User` con `name = "familia@example.com"` (del tutor)
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - **no** se crea `User` para el menor (regla 1 de "Decisión sobre `User`
    para menores": `solicitud.email == solicitud.email_tutor`),
  - se crea un `Socio` con `dni = "55222222"`, `categoria = "Menor"`,
    `email = "familia@example.com"`, `user = ""` (vacío),
    `tipo_tutor = "Socio"`, `tutor = <S_tutor.name>`,
    `grupo_familiar = G`,
    `estado = "Pendiente de Pago"`, `solicitud_origen = <name>`,
  - se agrega una nueva fila a `G.miembros` con `socio = <Socio menor>`,
    `rol = "Hijo"` (derivado de `rol_tutor = "Padre"`), `desde = hoy`,
  - la solicitud queda `Validada`, `socio_generado` poblado, `user_generado` vacío,
    `grupo_familiar_generado = G`,
  - el email del stub de pago se envía a `"familia@example.com"` (el tutor recibe
    el link para pagar la primera cuota del menor).

---

## Scenario: validar menor con tutor `Socio` — email único, **sí** se crea `User` para el menor

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "ana@example.com"` (email propio del menor),
`dni_tutor = "20111111"`, `email_tutor = "papa@example.com"` (email distinto),
`rol_tutor = "Padre"`
And ya existe un `Socio` `S_tutor` con `dni = "20111111"`, mayor de edad,
titular activo de `Grupo Familiar` `G`
And **no** existe ningún `User` con `name = "ana@example.com"` ni `username = "55222222"`
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - **se crea** un `User` para el menor con `name = "ana@example.com"`,
    `username = "55222222"`, `enabled = 1`, `user_type = "Website User"`, rol
    `Socio` (regla 2 de "Decisión sobre `User` para menores"),
  - se crea un `Socio` con `dni = "55222222"`, `categoria = "Menor"`,
    `email = "ana@example.com"`, `user = "ana@example.com"`,
    `tipo_tutor = "Socio"`, `tutor = <S_tutor.name>`,
    `grupo_familiar = G`, `estado = "Pendiente de Pago"`,
    `solicitud_origen = <name>`,
  - se agrega una nueva fila a `G.miembros` con `socio = <Socio menor>`,
    `rol = "Hijo"`, `desde = hoy`,
  - la solicitud queda `Validada`, `socio_generado` y `user_generado` poblados,
    `grupo_familiar_generado = G`,
  - el email del stub de pago se envía a `"papa@example.com"` (el **tutor**
    recibe el link aun cuando el menor tenga `User` propio: el tutor sigue
    siendo el responsable financiero).

---

## Scenario: validar menor con email ya tomado bloquea

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "ana@example.com"`
And `email_tutor = "papa@example.com"` (email distinto al del menor)
And ya existe un `User` con `name = "ana@example.com"` (de otra persona ajena
al grupo familiar)
When `Secretaria` ejecuta la acción `Validar`
Then la transición falla con `frappe.ValidationError`
(mensaje: "El email del menor ya tiene cuenta en el portal; usá el mismo email
del tutor o pedí al solicitante uno distinto")
And no se crea `Socio`, ni `User`, ni `Grupo Familiar`
And la solicitud permanece en `workflow_state = "Pendiente"`.

---

## Scenario: validar menor con tutor **no Socio** — email compartido con tutor

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "familia@example.com"`,
`dni_tutor = "20111111"`, `nombre_tutor = "Juan"`, `apellido_tutor = "Pérez"`,
`email_tutor = "familia@example.com"` (mismo email que el menor),
`rol_tutor = "Padre"` (más demás datos de contacto y
`fecha_nacimiento_tutor` mayor de 18)
And **no** existe ningún `Socio` con `dni = "20111111"`
And **no** existe ningún `Tutor No Socio` con `dni = "20111111"`
And no existe `User` con `name = "familia@example.com"` ni `username = "20111111"`
When `Secretaria` ejecuta la acción `Validar`
Then en una sola transacción:
  - se crea un `Tutor No Socio` `T_padre` con todos los datos declarados del tutor,
  - se provisiona un `User` para `T_padre` con `name = "familia@example.com"`,
    `username = "20111111"` (el tutor podrá pagar y gestionar desde el portal),
  - se crea un `Grupo Familiar` `G` con `titulares` = una sola fila
    `{tipo_titular: "Tutor No Socio", titular: T_padre, es_principal: 1, rol: <rol_tutor>}`,
  - **no** se crea `User` para el menor (regla 1: email compartido con tutor),
  - se crea un `Socio` `S_menor` con `dni = "55222222"`, `categoria = "Menor"`,
    `email = "familia@example.com"`, `user = ""` (vacío),
    `tipo_tutor = "Tutor No Socio"`, `tutor = T_padre`,
    `grupo_familiar = G`, `estado = "Pendiente de Pago"`,
    `solicitud_origen = <name>`,
  - se agrega una fila a `G.miembros` con `socio = S_menor`, `rol = "Hijo"`,
    `desde = hoy`,
  - la solicitud queda `Validada`, `socio_generado = S_menor`,
    `user_generado = ""`, `grupo_familiar_generado = G`,
  - el email del stub de pago se envía a `familia@example.com`.
And si **cualquier paso** falla, la transacción se aborta (no queda
`Tutor No Socio` huérfano sin grupo, ni grupo sin titulares, etc.).

---

## Scenario: validar menor con tutor **no Socio** — email único para el menor

Given una `Solicitud de Asociación` con `categoria_solicitada = "Menor"`,
`dni = "55222222"`, `email = "ana@example.com"` (email propio del menor),
`dni_tutor = "20111111"`, `nombre_tutor = "Juan"`, `apellido_tutor = "Pérez"`,
`email_tutor = "papa@example.com"`, `rol_tutor = "Padre"`
And **no** existen ni `Socio` ni `Tutor No Socio` con `dni = "20111111"`
And no existen `User` con `name` en `{"papa@example.com", "ana@example.com"}`
ni con `username` en `{"20111111", "55222222"}`
When `Secretaria` ejecuta `Validar`
Then en una sola transacción:
  - se crea `T_padre` (`Tutor No Socio`) + su `User` (`name = "papa@example.com"`,
    `username = "20111111"`),
  - se crea `G` (`Grupo Familiar`) con `T_padre` como único titular activo,
  - **se crea** un `User` para el menor con `name = "ana@example.com"`,
    `username = "55222222"`, rol `Socio` (regla 2: email único y no tomado),
  - se crea `S_menor` con `user = "ana@example.com"`, demás datos como en el
    escenario anterior,
  - el email del stub de pago se envía a `papa@example.com` (al tutor, no al menor).

> **Nota sobre cotitulares (padre + madre):** la Solicitud carga **un** tutor.
> Si ambos padres son adultos responsables del grupo, Secretaría agrega al
> segundo como cotitular (`es_principal = 0`) editando el `Grupo Familiar`
> después de validar al primer menor. No se carga directamente desde el Web
> Form público en Sprint 1.

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

## Scenario: validar con DNI ya registrado como `Socio` bloquea

Given una `Solicitud de Asociación` con `dni` = "30123456"
And ya existe un `Socio` con ese `dni`
When `Secretaria` intenta `Validar` la solicitud
Then la transición falla con `frappe.ValidationError`
(mensaje: "DNI ya registrado como Socio")
And la solicitud permanece en `Pendiente` (no pasa a `Validada`)
And Secretaría puede pasarla a `Rechazada` con motivo "DNI duplicado".

---

## Scenario: validar con DNI ya registrado como `Tutor No Socio` bloquea

Given una `Solicitud de Asociación` con `categoria_solicitada` ≠ `"Menor"`,
`dni` = "30123456"
And ya existe un `Tutor No Socio` activo con ese `dni` (es el caso del padre
que asoció a sus hijos al club y ahora quiere asociarse él mismo)
When `Secretaria` intenta `Validar` la solicitud
Then la transición falla con `frappe.ValidationError`
(mensaje: "DNI ya está registrado como Tutor No Socio; Secretaría debe migrar
manualmente el registro a Socio antes de validar")
And no se crea `Socio`, ni `User`, ni `Grupo Familiar`
And la solicitud permanece en `Pendiente`.

> La promoción automática `Tutor No Socio` → `Socio` (reutilizando `User`,
> reasignando referencias de `Socio.tutor` apuntando al nuevo Socio y
> transfiriendo titularidad del grupo) queda **fuera de scope Sprint 1**. Se
> cubre en un sprint dedicado de migración.

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

## Scenario: endpoint público `actualizar_solicitud` con token válido permite reenvío

Given una `Solicitud de Asociación` `SOL-2026-0001` con
`workflow_state = "Requiere Corrección"`, `token_seguimiento = "tk-abc"`
And un endpoint whitelisted `actualizar_solicitud(token, payload)` con
`allow_guest=True`
When un Guest llama al endpoint con `token = "tk-abc"` y un `payload` que
actualiza `dni_dorso` (Attach) y `telefono`
Then la solicitud queda actualizada con los nuevos valores
And `workflow_state` pasa nuevamente a `"Pendiente"` (re-entra en la cola)
And los adjuntos anteriores quedan referenciados en el historial / versiones
de Frappe (auditoría)
And el endpoint responde 200 OK con un mensaje de confirmación
(sin exponer el `name` del documento).

---

## Scenario: endpoint público `actualizar_solicitud` rechaza campos no editables

Given una `Solicitud de Asociación` `SOL-2026-0001` con
`workflow_state = "Requiere Corrección"`, `token_seguimiento = "tk-abc"`
When un Guest llama al endpoint con `token = "tk-abc"` y un `payload` que
intenta modificar `workflow_state`, `validado_por`, `socio_generado`,
`enviado_desde_ip` o cualquier otro campo de auditoría / sistema
Then el endpoint **ignora silenciosamente** esos campos (no los aplica) o
falla con `frappe.ValidationError` (decisión de implementación: lista blanca
explícita de campos editables por Guest)
And nunca se exfiltra el estado actual de esos campos en la respuesta de error
And el resto de los campos editables sí se aplican (degradación segura: el
ataque no rompe el flujo legítimo).

(La lista blanca de campos editables vive en el código del endpoint y se
documenta como constante: `CAMPOS_EDITABLES_POR_GUEST = {"telefono",
"domicilio", "localidad", "provincia", "codigo_postal", "dni_frente",
"dni_dorso", "foto_perfil", "ficha_medica", "comprobante_domicilio", ...}`.)

---

## Scenario: endpoint público `actualizar_solicitud` rechaza token inválido o vencido

Given una `Solicitud de Asociación` con `token_seguimiento = "tk-abc"`,
`workflow_state = "Requiere Corrección"`
When un Guest llama al endpoint con `token = "tk-otra"` (no existe ninguna
solicitud con ese token), o con un token correcto pero la solicitud está en
un estado distinto de `"Requiere Corrección"` (p. ej. `"Pendiente"` o
`"Validada"`)
Then el endpoint responde `404 Not Found` (sin distinguir entre "token
inexistente" y "estado no permite corrección"; evita oracle attack)
And no se aplica ningún cambio
And no se filtra información de existencia/estado del documento.

---

## Scenario: endpoint público `actualizar_solicitud` aplica el mismo rate-limit

Given el mismo umbral de rate-limit del alta (`5/10min por IP`)
When una IP X envía 6 llamadas al endpoint `actualizar_solicitud` en menos
de 10 minutos
Then la sexta es rechazada con HTTP 429
And se registra el intento en `frappe.log_error`.

(Implementación: el rate-limit se aplica a la combinación `IP + endpoint`,
no globalmente al sitio.)

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

## Plan de commits (Sprint 1)

| # | Tema | Tests rojos primero |
|---|---|---|
| 1 | DocType `Solicitud de Asociación` (JSON + autoname + permisos) + tests unitarios | sí — `test_solicitud_asociacion.py::test_doctype_*` |
| 2 | Web Form público + validaciones server-side (incluye rate-limit, token, IP detrás de proxy, IP en `enviado_desde_ip`) | sí — `test_solicitud_asociacion.py::test_web_form_*` |
| 3 | Workflow fixture (`Pendiente / Requiere Corrección / Validada / Rechazada`) + `before_save` de auditoría (`validado_por/en`, etc.) | sí — `test_workflow_solicitud_asociacion.py` |
| 4 | Service `ensure_grupo_for_socio` + `validar_solicitud` (adulto, menor-con-Socio, menor-con-TNS, los 3 sub-flujos de email del menor) + bloqueos (G2 DNI ya TNS, G3 email ya tomado, etc.) | sí — `test_workflow_solicitud_asociacion.py::test_validar_*` |
| 5 | Email templates + stub de pago (`pago_stub`) + tests de escape XSS en `motivos_rechazo` + endpoint público `solicitar_correccion` por token | sí — `test_solicitud_asociacion_emails.py`, `test_correccion_publica.py` |
| 6 | Migrar `Socio.solicitud_origen` de `Data` → `Link "Solicitud de Asociación"` + test que verifica la integridad referencial | sí — `test_socio_referencia_solicitud.py` (nuevo) |

Cada commit con sus tests en verde antes de pasar al siguiente. La rama
`develop` debe quedar siempre estable.

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
    crea `User` si y solo si el email no está tomado y no comparte el del tutor;
    **nunca** genera email técnico; devuelve `None` si el menor queda sin User.
    Es el servicio que ejecuta la "Decisión sobre `User` para menores" (3 reglas).
  - `members/services/grupo_familiar.py::ensure_grupo_for_socio(socio_doc, tutor_doc=None)` —
    crea `Grupo Familiar` nuevo si el solicitante es adulto, o agrega al menor al
    `Grupo Familiar` del tutor existente. **Este servicio no existe todavía; se
    crea en el commit 4 del Sprint 1.**

- **Migración de `Socio.solicitud_origen` (commit 6 del sprint):** hoy es `Data
  (string)` porque el DocType `Solicitud de Asociación` no existía en Sprint 0.
  En Sprint 1 commit 6 se migra a `Link → "Solicitud de Asociación"`. La
  migración requiere:
  - actualizar `socio.json` con el nuevo `fieldtype` y `options`,
  - un patch en `patches.txt` que mapee strings huérfanos a `name`s del nuevo
    DocType (o los limpie si no se encuentran),
  - test que verifica que un `Socio` con `solicitud_origen` apuntando a una
    `Solicitud de Asociación` válida puede leerse y la referencia es navegable.
- Auditoría:
  - `before_save` del DocType setea `validado_por/en`, `rechazado_por/en`,
    `correccion_solicitada_por/en` según la transición de `workflow_state`.
  - Si `workflow_state` no cambia, los campos de auditoría se mantienen
    (no se sobreescriben en saves "intrascendentes").
- Tests:
  - `members/doctype/solicitud_asociacion/test_solicitud_asociacion.py`
    → alta Guest, validaciones de campos, rate-limit, validación MIME de ficha
    médica, IP detrás de proxy (`X-Forwarded-For`), `token_seguimiento` no
    enumerable, autoname.
  - `members/doctype/solicitud_asociacion/test_workflow_solicitud_asociacion.py`
    → transiciones (validar adulto / validar menor con tutor Socio / validar
    menor con tutor No Socio / validar segundo menor / rechazar / corrección),
    los 3 sub-flujos de email del menor (compartido, único+libre, único+tomado),
    bloqueo por DNI ya Socio, bloqueo por DNI ya Tutor No Socio,
    idempotencia, auditoría de timestamps, `familiares_existentes_dnis`
    declarativo.
  - `members/tests/test_solicitud_asociacion_isolation.py`
    → Guest no lee, Socio no lee, Secretaría sí.
  - `members/tests/test_solicitud_asociacion_emails.py`
    → escape XSS en `motivos_rechazo`, contenido del email validada, link de
    pago stub no adivinable por enumeración.
  - `members/tests/test_correccion_publica.py` (Sprint 1 mantiene endpoint
    público de corrección)
    → token válido + estado `Requiere Corrección` permite actualizar adjuntos;
    token inválido o vencido → 404; scope limitado a la misma solicitud
    (no se puede modificar otra); campos no editables por Guest están
    protegidos (`workflow_state`, auditoría, etc.).
  - `members/tests/test_socio_referencia_solicitud.py` (commit 6)
    → migración `Socio.solicitud_origen` de Data → Link funciona; integridad
    referencial; lectura del Socio sigue accesible vía las reglas de aislamiento
    de Sprint 0.

- En `hooks.py` (al implementar):
  - `has_website_permission` / `permission_query_conditions` para
    `Solicitud de Asociación` si se permite portal de seguimiento.
  - No exponer la solicitud por `/api/resource/` a Guest.
