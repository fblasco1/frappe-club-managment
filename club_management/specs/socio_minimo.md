# Spec: Socio mínimo (Sprint 0)

Given/When/Then scenarios para el **DocType `Socio`** en su versión mínima viable.
Esta spec habilita el flujo `Solicitud de Asociación → Validación → Activación por pago`
y desbloquea la rama de activación del webhook Cobros Plus ya existente.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`
**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

**Ubicación del DocType:** `club_management/members/doctype/socio/`
**Módulo Frappe:** `Members` (a agregar a `modules.txt`)

---

## Objetivo y alcance

Esta primera entrega del DocType `Socio` cubre el flujo prioritario
*Solicitud → Validación → Pago de primera cuota → Activación*, e incluye:

- Datos personales completos (incluida `nacionalidad`).
- Categoría obligatoria; `Vitalicio` no asignable manualmente.
- Adjuntos obligatorios (foto, DNI ambas caras, ficha médica validada por MIME/tamaño).
- Auditoría server-side de transiciones de estado y alta validada.
- Política de `User`: opcional para menores cuyo email es compartido por su tutor.
- Login DNI / email para Socios con `User` propio (el número de socio es el `name`
  entero, no un identificador de login).
- `Grupo Familiar` y `tutor` integrados desde Sprint 0 (DocType `Grupo Familiar`
  definido en su propio spec, `grupo_familiar_minimo.md`).

Quedan **fuera** de Sprint 0 (cubiertos por `socios_categoria_validacion.md`):

- Tabla de cuotas por categoría en `Club Settings`.
- Job programado de promoción a `Vitalicio` a los 25 años (este sprint solo
  bloquea su asignación manual).
- Workspace `Secretaría` completo y Report "Socios pendientes de validación".
- Lógica de descuento por hermanos.

---

## Campos propuestos


### Identidad (naming)

| Campo           | Tipo | Reqd | Read-only en UI | Comentario                                                  |
| --------------- | ---- | ---- | --------------- | ----------------------------------------------------------- |
| `numero_socio`  | Int  | sí   | no              | **Es el `name` (PK)**. Histórico y autoincremental; vacío en alta nueva ⇒ `MAX + 1`. Inmutable (`allow_rename = 0`) |
| `fecha_ingreso` | Date | no   | no              | Ingreso administrativo (año de ingreso); default `Today`. Distinto de `fecha_alta` |

### Datos personales

| Campo              | Tipo             | Reqd          | Read-only en UI | Comentario                                                  |
| ------------------ | ---------------- | ------------- | --------------- | ----------------------------------------------------------- |
| `nombre`           | Data             | sí            | no              | Nombre/s                                                    |
| `apellido`         | Data             | sí            | no              | Apellido/s                                                  |
| `dni`              | Data             | sí (`unique`) | no              | Identificador AR único por persona                          |
| `nacionalidad`     | Link → `Country` | **sí**        | no              | Default `"Argentina"`                                       |
| `fecha_nacimiento` | Date             | sí            | no              |                                                             |
| `genero`           | Select           | **sí**        | no              | `Masculino` / `Femenino` / `Otro` / `Prefiero no decir`     |
| `email`            | Data (Email)     | **sí**        | no              | **No único**: puede repetirse entre miembros de una familia o entre un menor y su tutor |
| `telefono`         | Data             | **sí**        | no              |                                                             |
| `domicilio`        | Small Text       | **sí**        | no              |                                                             |
| `localidad`        | Data             | **sí**        | no              |                                                             |
| `provincia`        | Data             | **sí**        | no              |                                                             |
| `codigo_postal`    | Data             | **sí**        | no              |                                                             |

### Estado y categoría

| Campo        | Tipo   | Reqd   | Read-only en UI | Comentario                                                  |
| ------------ | ------ | ------ | --------------- | ----------------------------------------------------------- |
| `estado`     | Select | sí     | **sí**          | Ver máquina de estados abajo                                |
| `categoria`  | Select | **sí** | no              | `Activo` / `Menor` / `Adherente` / `Jubilado` / `Vitalicio` |
| `fecha_alta` | Date   | no     | **sí**          | Se setea la primera vez que `estado` llega a `Activo`       |

### Vínculos (User, Familia, Trazabilidad)

| Campo              | Tipo                                       | Reqd    | Read-only en UI | Comentario                                                  |
| ------------------ | ------------------------------------------ | ------- | --------------- | ----------------------------------------------------------- |
| `user`             | Link → `User`                              | no      | no              | `unique` cuando está presente. **Opcional**: ver "Política de User" abajo |
| `grupo_familiar`   | Link → `Grupo Familiar`                    | depende | no              | **Obligatorio si `categoria = "Menor"`**. Ver `grupo_familiar_minimo.md` |
| `tipo_tutor`       | Select                                     | depende | no              | **Obligatorio si `categoria = "Menor"`**. Valores: `"Socio"` / `"Tutor No Socio"` |
| `tutor`            | Dynamic Link (`options = tipo_tutor`)      | depende | no              | **Obligatorio si `categoria = "Menor"`**. Apunta a `Socio` o `Tutor No Socio` según `tipo_tutor`; debe ser mayor de 18 y figurar como **titular activo** (principal o cotitular) en `grupo_familiar.titulares` |
| `solicitud_origen` | Link → `Solicitud de Asociación`           | no      | **sí**          | Trazabilidad del origen                                     |

### Documentos adjuntos

| Campo          | Tipo         | Reqd   | Read-only en UI | Comentario                                                  |
| -------------- | ------------ | ------ | --------------- | ----------------------------------------------------------- |
| `foto_perfil`  | Attach Image | **sí** | no              |                                                             |
| `dni_frente`   | Attach       | **sí** | no              | Copiado desde la Solicitud al validar                       |
| `dni_dorso`    | Attach       | **sí** | no              | Idem                                                        |
| `ficha_medica` | Attach       | **sí** | no              | PDF / JPEG / PNG, ≤ 5MB; firmado por profesional médico     |

### Auditoría (todos `read-only` en UI; setean desde server-side)

| Campo                          | Tipo          | Reqd | Comentario                                                  |
| ------------------------------ | ------------- | ---- | ----------------------------------------------------------- |
| `alta_validada_por`            | Link → `User` | no   | Quién ejecutó la transición `Validar` de la Solicitud origen |
| `alta_validada_en`             | Datetime      | no   | Timestamp de la creación al validar la Solicitud            |
| `ultimo_cambio_estado_por`     | Link → `User` | no   | Última mutación de `estado` (validación, pago, job Vitalicio…) |
| `ultimo_cambio_estado_en`      | Datetime      | no   | Timestamp del último cambio de `estado`                     |
| `motivo_ultimo_cambio_estado`  | Small Text    | no   | Texto libre o código del motivo (ej. `"Pago confirmado SI-0001"`) |

> Frappe ya provee `owner`, `creation`, `modified`, `modified_by` automáticamente.
> Los campos de arriba **complementan** esa metadata para auditar específicamente
> las transiciones de estado y la procedencia del alta.


**Naming y "número de socio":** `autoname = "field:numero_socio"` (`naming_rule = "By fieldname"`).
El **número de socio** es un entero histórico y autoincremental que **es** el `name`
(PK) del documento; es único e inmutable (`allow_rename = 0`). El DNI también es único
pero es un identificador externo, no la PK del DocType.

Reglas de asignación (controller `Socio.before_insert`):

- **Migración de base histórica (alta manual desde el Desk):** Secretaría carga
  `numero_socio` con el número real del socio (p. ej. `1500`). Ese valor se usa
  tal cual como `name` para respetar la numeración existente del club.
- **Altas nuevas (aprobación de `Solicitud Asociacion` vía web):** si `numero_socio`
  viene vacío, el controller calcula `MAX(numero_socio) + 1` y lo asigna al campo y
  al `name`. La consulta usa el **query builder de Frappe** (`frappe.qb` + `Max`),
  DB-agnóstico y compatible con **PostgreSQL v14**; **no** se usa SQL crudo con
  `CAST(... AS UNSIGNED)` (sintaxis MariaDB que falla en PostgreSQL).
- **Concurrencia:** `MAX + 1` tiene una ventana de carrera teórica. El backstop es
  el `name` (PK único): dos inserts simultáneos con el mismo número fallan con
  `DuplicateEntryError` (fallo seguro, sin corrupción). El volumen del club (altas
  una a una) hace despreciable el riesgo.
- **Orden operativo:** migrar primero la base histórica (1500 socios) y recién
  después habilitar altas web, para que el autoincremento parta del máximo real.
- **Unicidad por PK (no `unique` de campo):** `numero_socio` **no** lleva
  `"unique": 1`. La unicidad ya la garantiza el `name` (PK), y un `unique` de campo
  sería peligroso al correr `bench migrate` sobre una base con filas `Socio`
  preexistentes: Frappe crea la columna `Int` con `DEFAULT 0`, por lo que todas las
  filas legacy quedarían en `0` y un índice único colisionaría. Los registros
  legacy quedan en `numero_socio = 0` hasta que se los renumere en la migración.

**`fecha_ingreso` vs `fecha_alta`:** `fecha_ingreso` (Date, default `Today`) registra
el ingreso administrativo del socio (año de ingreso) sin ensuciar el `name`.
Es distinta de `fecha_alta`, que marca el primer pase a `Activo`.

### Listado Desk (`Socio`)

Given Secretaría abre la lista de socios en Desk
When se muestra la grilla por defecto del DocType `Socio`
Then las columnas visibles son, en este orden: `Número de Socio`, `Nombre Apellido`,
`Estado`, `Categoría`, `Actividad`
And `Nombre Apellido` muestra el campo calculado `nombre_completo` (`Apellido, Nombre/s`)
And la lista ordena por `numero_socio` ascendente

**Política de User (login del portal):**

En Frappe, `User.name` es el email y `User.email` es **único**. Como en este modelo
el email del `Socio` **no** es único (varios miembros de una familia pueden compartir
email), no toda alta de `Socio` puede tener un `User` propio.

Regla:

- **Adulto** (`categoria` ≠ `"Menor"`): se crea siempre `User`.
  - `User.name` = `User.email` = `Socio.email`.
  - `User.username` = `Socio.dni`.
  - `User.enabled` = 1, `user_type` = `"Website User"`, rol `Socio`.
  - **Si el email ya está tomado** por otro `User` (caso raro en adultos: dos adultos
    sin email propio): la validación de la Solicitud **falla** y exige email distinto
    o ratifica que la persona debe usar la cuenta existente.
- **Menor** (`categoria = "Menor"`):
  - Si el email **no** está tomado: se crea `User` igual que un adulto.
  - Si el email **ya está tomado** (típicamente por su tutor): **no se crea `User`**
    para el menor. El campo `Socio.user` queda vacío. La gestión la hace el tutor
    desde su propio portal vía el `Grupo Familiar`.

**No se crean emails técnicos sintéticos.** Si un `Socio` no tiene `User` propio,
es porque está bajo la gestión de su tutor.

**Login (solo aplica a Socios con `User` propio)**

Para los socios que tienen `User` propio, el login se hace con **email** o con **DNI**
(el DNI es el `User.username` persistido; Frappe lo resuelve con
`allow_login_using_user_name = 1`).

> **Cambio de diseño (refactor de naming a número de socio entero):** al pasar el
> `name` del `Socio` a un entero, el login por número de socio **se elimina** para
> evitar la ambigüedad con el DNI (ambos serían numéricos). El `auth_hook`
> `resolve_login_user` mantiene la traducción `TNS-{YYYY}-{####} → Tutor No Socio.user`,
> pero **ya no** reescribe identificadores de `Socio`. Ver `login_dual.md`.

**Estados (`estado`):**

```
Pendiente de Validación  → estado inicial al crear desde Solicitud validada
        ↓ (cobro de primera cuota confirmado por webhook)
Pendiente de Pago        → opcional; se omite si la creación ocurre tras pago confirmado
        ↓
Activo                   → operación normal; setea `fecha_alta` la primera vez
        ↓ / ↑
Moroso                   → sin cuota pagada en el período corriente
Requiere Corrección      → datos inválidos detectados
Vitalicio                → automático tras 25 años (sprint posterior)
Inactivo                 → baja
```

---

## Scenario: `estado` no es editable directamente desde el formulario

Given un usuario con rol `Secretaria` o `System Manager`
And un `Socio` existente con `estado` = `Pendiente de Validación`
When el usuario intenta cambiar `estado` directamente desde el formulario y guardar
Then el guardado falla con `frappe.PermissionError` o `frappe.ValidationError`
And el `estado` persistido no cambia
And el único camino válido para mutar `estado` es la API server-side
(`validar_socio`, hooks de pago confirmado, o el job de Vitalicio del sprint siguiente).

---

## Scenario: `fecha_alta` se setea solo la primera vez que `estado` llega a `Activo`

Given un `Socio` con `fecha_alta` vacío y `estado` en cualquier valor ≠ `Activo`
When el flujo server-side transiciona `estado` a `Activo`
Then `fecha_alta` se setea a la fecha del servidor (hoy) en esa misma transición
And subsiguientes transiciones desde otros estados a `Activo` **no sobreescriben** `fecha_alta`
And consultar `fecha_alta` luego siempre devuelve la fecha del primer alta.

---

## Scenario: `dni` único en alta

Given existe un `Socio` con `dni` = "30123456"
When un proceso server-side intenta crear otro `Socio` con `dni` = "30123456"
Then la inserción falla con `frappe.DuplicateEntryError` (o ValidationError equivalente)
And no se crea un segundo registro.

---

## Scenario: `email` puede repetirse entre socios (familia)

Given existe un `Socio` `S_padre` con `email` = "familia@example.com"
When un proceso server-side crea otro `Socio` `S_hijo_menor` con el mismo
`email` = "familia@example.com" y `dni` distinto
Then la inserción tiene éxito
And ambos `Socio` quedan persistidos con el mismo `email`
And las notificaciones por email a `S_hijo_menor` se envían a "familia@example.com"
(en sprints posteriores se podrá decidir notificar solo al tutor; en Sprint 0
se notifica al `Socio.email` tal como está).

---

## Scenario: el `User` del portal se crea con `username = dni` y `User.email` libre

Given un `Socio` `S1` con `dni` = "30123456" y `email` = "familia@example.com"
And **no** existe ningún `User` con `name` = "familia@example.com"
And no existe ningún `User` con `username` = "30123456"
When un proceso server-side crea el `User` asociado y enlaza `S1.user`
Then se crea un `User` con `name` = "familia@example.com",
`username` = "30123456", `enabled` = 1, `user_type` = "Website User",
rol `Socio`
And `S1.user` queda enlazado a ese `User`
And el usuario puede iniciar sesión usando "30123456" como `username` y su contraseña.

---

## Scenario: el `Socio` menor con email compartido por su tutor queda sin `User` propio

Given un `Socio` `S_padre` con `dni` = "20111111", `email` = "familia@example.com",
`categoria` = `"Activo"`, ya enlazado a `User` con `name` = "familia@example.com"
And un proceso server-side está creando `S_hijo` con `dni` = "55222222",
`email` = "familia@example.com", `categoria` = `"Menor"`,
`tutor` = `S_padre`, `grupo_familiar` = `<grupo de S_padre>`
When se ejecuta la creación
Then el `Socio` `S_hijo` se crea con `user` vacío (no se crea `User` nuevo)
And **no** se intenta crear un email técnico sintético
And `S_hijo.tutor` apunta a `S_padre`
And la gestión del menor desde el portal la hace `S_padre` vía el `Grupo Familiar`
(scope cubierto en `grupo_familiar_minimo.md`).

---

## Scenario: el `Socio` adulto con email ya tomado bloquea la creación

Given un `Socio` `S_padre` con `email` = "familia@example.com" ya enlazado a `User`
con `name` = "familia@example.com"
And un proceso server-side intenta crear `S_otro` adulto con
`email` = "familia@example.com" y `categoria` = `"Activo"`
When se ejecuta la creación
Then la operación falla con `frappe.ValidationError`
(mensaje del estilo: "El email ya tiene cuenta en el portal; usá un email distinto
o coordiná con Secretaría")
And no se crea el `Socio`
And no se crea ningún `User` adicional.

---

## Scenario: `Socio.user` es 1 a 1 (no se puede compartir entre dos socios)

Given un `Socio` `S1` ya enlazado a `User` `U`
When un proceso server-side intenta enlazar `S2.user = U`
Then la operación falla con error de unicidad
(`unique` en la propiedad del campo `user` del DocType).

---

## Scenario: login dual — DNI funciona como username

Given un `Socio` con `dni = "30123456"` enlazado a un `User`
con `username = "30123456"` y password conocido
When ese usuario intenta iniciar sesión usando `"30123456"` como identificador
Then la autenticación tiene éxito
And se crea una sesión válida para ese `User`
And el `permission_query_conditions` del rol `Socio` filtra las consultas a su
propio documento.

---

## Scenario: login — Número de Socio numérico NO se intercepta

Given un `Socio` con `name = "1500"` (número de socio entero), `dni = "30123456"`
y `user = "ana@example.com"`
And el `auth_hook` `resolve_login_user` está registrado en `hooks.py` (`auth_hooks`)
When el usuario intenta iniciar sesión usando `"1500"` como identificador
Then el `auth_hook` **no** reescribe el identificador (el login por número de socio
fue eliminado en el refactor de naming para evitar ambigüedad con el DNI)
And Frappe procesa el identificador por su flujo estándar (email / `username`),
fallando con error de credenciales si no corresponde a ningún `User`.

---

## Scenario: login — identificador cae al flujo normal de Frappe

Given un identificador de login que **no** matchea el formato `TNS-{YYYY}-{####}`
(por ejemplo "30123456", "ana@example.com", "1500")
When el usuario intenta iniciar sesión con ese identificador
Then el `auth_hook` no intercepta y delega al flujo estándar de Frappe (login por
email o por `username = DNI`)
And el mensaje de error mostrado al usuario no distingue entre "no existe" y
"contraseña incorrecta" (evitar enumeración de socios).

---

## Scenario: `ficha_medica` rechaza tipos MIME y tamaños fuera del rango

Given un `Socio` en alta o edición
When se intenta adjuntar como `ficha_medica` un archivo cuyo tipo MIME **no** es
`application/pdf`, `image/jpeg` ni `image/png`
Then la validación falla con `frappe.ValidationError("Tipo de archivo no permitido")`
And el archivo no se persiste
And el campo `ficha_medica` mantiene su valor anterior (o vacío si era alta).

Given el mismo `Socio`
When se intenta adjuntar como `ficha_medica` un archivo con tipo MIME válido pero
tamaño > 5 MB
Then la validación falla con `frappe.ValidationError("Archivo excede 5 MB")`
And el archivo no se persiste.

Given el mismo `Socio`
When se adjunta un PDF de 1 MB como `ficha_medica`
Then el archivo se persiste correctamente
And `ficha_medica` contiene la URL al archivo dentro de `/files/` o `/private/files/`.

---

## Scenario: rol `Socio` solo ve su propio documento

Given dos `Socio` distintos `S1` y `S2`, cada uno enlazado a su propio `User` `u1` / `u2`
And `u1` y `u2` tienen rol `Socio` (no `Secretaria`)
When `u1` consulta el listado o el documento de `S2`
Then la operación devuelve cero filas en lista
And la apertura directa del documento de `S2` falla con `frappe.PermissionError`
And `u1` sí puede leer su propio `S1` con todos los campos del DocPerm.

(Implementación: `permission_query_conditions` (filtra listas) y `has_permission`
(filtra `get_doc` vía REST/portal) registrados en `hooks.py` para el rol `Socio`.
**Nota de tests:** en Frappe v15+, `frappe.get_doc(doctype, name)` desde código
Python server-side no dispara los hooks `has_permission`. Para testear el caso
"abrir un Socio ajeno falla con PermissionError" se usa
`frappe.has_permission(doctype, "read", doc=name, user=..., throw=True)`, que es
la API que `frappe.client.get` —el endpoint REST que ejerce el portal— invoca
bajo el capó.)

---

## Scenario: `Secretaria` ve y edita todos los socios

Given un usuario con rol `Secretaria`
When consulta el listado o cualquier documento `Socio`
Then ve todos los socios sin filtro de propiedad
And puede editar campos editables (no `estado`, no `fecha_alta`)
And no puede borrar (`delete` solo `System Manager`).

---

## Scenario: `categoria = "Menor"` exige `tipo_tutor`, `tutor` y `grupo_familiar`

Given un proceso server-side intenta crear un `Socio` con
`categoria` = `"Menor"`, `fecha_nacimiento` = (hoy − 12 años)
And `tipo_tutor` / `tutor` / `grupo_familiar` parcialmente vacíos
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Socio menor requiere `tipo_tutor`, `tutor` y `grupo_familiar`")
And el documento no se persiste.

Given el mismo intento con `tipo_tutor = "Socio"`, `tutor = <Socio_T>`
donde `T.fecha_nacimiento` lo deja en (hoy − 16 años)
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Tutor debe ser mayor de 18 años")
And el documento no se persiste.

Given el mismo intento con `tipo_tutor = "Socio"`, `tutor` mayor de 18 años,
pero `tutor` **no** figura como titular activo en `grupo_familiar.titulares`
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Tutor debe ser titular activo del Grupo Familiar del menor")
And el documento no se persiste.

Given el mismo intento, ahora con `tipo_tutor` y `tutor` consistentes con el
grupo familiar (todas las validaciones cumplidas)
When se ejecuta `insert()`
Then la operación tiene éxito y el `Socio` se persiste con `categoria = "Menor"`.

---

## Scenario: menor con tutor `Tutor No Socio` exige que sea titular activo del grupo

Given un proceso intenta crear un `Socio` con `categoria = "Menor"`,
`tipo_tutor = "Tutor No Socio"`, `tutor = T_padre`,
`grupo_familiar = G`
And `T_padre` figura como **titular activo** en `G.titulares` (principal o
cotitular, con `hasta` vacío)
And `T_padre` es mayor de 18 años
When se ejecuta `insert()`
Then la operación tiene éxito y el `Socio` se persiste como menor de `T_padre`.

Given el mismo intento pero `T_padre` **no** está en `G.titulares` activo
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Tutor debe ser titular activo del Grupo Familiar del menor")
And el menor no se persiste.

Given un intento con `tipo_tutor = "Tutor No Socio"` y `tutor = T_x` con
`fecha_nacimiento` que lo deja en (hoy − 17 años)
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Tutor debe ser mayor de 18 años")
And el menor no se persiste.

---

## Scenario: `categoria ≠ "Menor"` no exige `tutor` ni `grupo_familiar`

Given un proceso crea un `Socio` adulto con `categoria` ∈ `{"Activo", "Adherente",
"Jubilado"}` y `tutor`/`grupo_familiar` vacíos
When se ejecuta `insert()`
Then la operación tiene éxito y el `Socio` se persiste sin tutor ni grupo familiar
(el adulto puede asociarse a un `Grupo Familiar` más tarde de forma opcional).

---

## Scenario: `Vitalicio` solo se asigna por proceso server-side (no manual)

Given un `Socio` con `estado` ≠ `"Vitalicio"`
When `Secretaria` intenta setear `estado = "Vitalicio"` desde el formulario
Then el guardado falla (mismo bloqueo que el Scenario inicial de `estado` read-only)
And la única vía válida para asignar `"Vitalicio"` es el job programado que evalúa
`fecha_alta` y antigüedad ≥ 25 años (spec `socios_categoria_validacion.md`).

(Este sprint **no** implementa el job; solo bloquea la asignación manual.)

---

## Scenario: cambio de estado registra auditoría server-side

Given un `Socio` con `estado` = `"Pendiente de Pago"`,
`ultimo_cambio_estado_por` vacío, `ultimo_cambio_estado_en` vacío
And un proceso server-side ejecuta como `Secretaria` "ana@example.com" una
transición a `estado = "Activo"` con motivo "Pago confirmado SI-0001"
When se persiste la transición
Then `Socio.estado` = `"Activo"`
And `Socio.ultimo_cambio_estado_por` = `"ana@example.com"`
And `Socio.ultimo_cambio_estado_en` ≈ ahora (tolerancia ≤ 5s)
And `Socio.motivo_ultimo_cambio_estado` = `"Pago confirmado SI-0001"`
And `Socio.fecha_alta` se setea a la fecha de hoy (primer alta).

---

## Scenario: webhook Cobros Plus activa al `Socio` linkeado en la `Sales Invoice`

Given un `Socio` con `estado` = `Pendiente de Pago`
And una `Sales Invoice` cuya `name` coincide con `cod_trx` del webhook
And en la `Sales Invoice` existe un campo custom (`socio` o `custom_socio`) que apunta al `Socio`
When llega un webhook Cobros Plus válido (hash correcto) que concilia esa factura
Then el `Payment Entry` se crea y se submitea (lógica ya existente)
And el `Socio` pasa a `estado` = `Activo`
And `fecha_alta` se setea a la fecha del servidor (primera vez)
And el campo `solicitud_origen` (si existe) queda intacto.

(Esto re-usa `integrations/supervielle_webhook.py::_activate_socio_from_invoice`,
solo agrega el caso `Pendiente de Pago → Activo`).

---

## Notas de implementación (informativas, no testeables aquí)

- `module` del JSON debe ser `Members` y `modules.txt` debe incluir `Members`.
- Tests del DocType: `club_management/members/doctype/socio/test_socio.py` con `FrappeTestCase`.
- Test de aislamiento entre socios: `club_management/tests/test_socio_isolation.py`.
- Tests de tutor y grupo familiar: `club_management/tests/test_socio_familia.py`.
- El hook que activa al socio en pago confirmado vive en `integrations/supervielle_webhook.py`
  (ya implementado parcialmente); este sprint extiende el set de estados aceptados a
  `{"Moroso", "Pendiente", "Pendiente de Pago"}`.
- Habilitar `enable_login_by_username = 1` en `System Settings` (via `after_install`
  o documentación de despliegue) para que el login por DNI funcione.
- Registrar el `auth_hook` de login dual en `hooks.py`:
  ```python
  auth_hooks = ["club_management.members.auth.resolve_socio_login"]
  ```
  La función `resolve_socio_login` vive en `club_management/members/auth.py`.
- Validación de `ficha_medica` (MIME `application/pdf` / `image/jpeg` / `image/png`,
  tamaño ≤ 5 MB) en el `validate()` del controlador `Socio`. Se aplica también
  desde el Web Form de Solicitud (mismo helper reutilizado en
  `club_management/members/validations.py::validate_ficha_medica`).
- Validaciones de tutor / grupo familiar también en `validate()` del controlador.
  Reglas: si `categoria == "Menor"`, exigir `tutor` y `grupo_familiar`; verificar que
  `tutor.fecha_nacimiento` deje al tutor con ≥ 18 años; verificar que `tutor` sea
  miembro del mismo `grupo_familiar`.
- Hook `before_save` setea `ultimo_cambio_estado_por` = `frappe.session.user` y
  `ultimo_cambio_estado_en` = `frappe.utils.now()` cuando `estado` cambia.
  `motivo_ultimo_cambio_estado` debe pasarse explícitamente desde el caller
  (no se inventa).

