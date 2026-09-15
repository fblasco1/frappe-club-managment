# Spec: Tutor No Socio mínimo (Sprint 0)

Given/When/Then para el **DocType `Tutor No Socio`**, que representa a la persona
adulta responsable de uno o más `Socio` menores **sin ser ella misma Socio**.

Caso de uso típico: un padre/madre que asocia a dos hijos menores al club, pero
él/ella mismo/a no realiza actividad y no se asocia. Igual debe figurar como
titular del `Grupo Familiar` para gestionar cobros, contacto y trazabilidad, y
debe poder iniciar sesión en el portal para pagar las cuotas de los menores.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`
**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

**Ubicación del DocType:** `club_management/members/doctype/tutor_no_socio/`
**Módulo Frappe:** `Members`

---

## Objetivo y alcance

Sprint 0 entrega:

- DocType estándar `Tutor No Socio` con datos personales mínimos.
- Provisión de `User` del portal con la misma política que el `Socio` adulto
  (login dual DNI / serie `TNS-…`; sin emails técnicos).
- Vínculo opcional `socio_vinculado` por si en el futuro la misma persona se
  asocia (en cuyo caso conviven temporalmente; la conversión completa queda
  fuera de Sprint 0).
- Permisos: `Secretaria` y `System Manager` gestionan; el propio `Tutor No Socio`
  ve solo su propio documento vía `Tutor No Socio.user`.

Quedan **fuera** de Sprint 0:

- Migración automatizada de un `Tutor No Socio` a `Socio` cuando se asocia
  posteriormente (se documenta como flujo manual de Secretaría).
- Pantallas portal específicas para Tutor No Socio (sprints siguientes).

---

## Campos propuestos

### Datos personales

| Campo              | Tipo             | Reqd          | Read-only en UI | Comentario                                                  |
| ------------------ | ---------------- | ------------- | --------------- | ----------------------------------------------------------- |
| `nombre`           | Data             | sí            | no              | Nombre/s                                                    |
| `apellido`         | Data             | sí            | no              | Apellido/s                                                  |
| `dni`              | Data             | sí (`unique`) | no              | Identificador AR único por persona                          |
| `nacionalidad`     | Link → `Country` | **sí**        | no              | Default `"Argentina"`                                       |
| `fecha_nacimiento` | Date             | sí            | no              | Debe corresponder a mayor de 18 años                        |
| `genero`           | Select           | **sí**        | no              | `Masculino` / `Femenino` / `Otro` / `Prefiero no decir`     |
| `email`            | Data (Email)     | **sí**        | no              | **No único**: puede coincidir con el `Socio.email` de un familiar |
| `telefono`         | Data             | **sí**        | no              |                                                             |
| `domicilio`        | Small Text       | **sí**        | no              |                                                             |
| `localidad`        | Data             | **sí**        | no              |                                                             |
| `provincia`        | Data             | **sí**        | no              |                                                             |
| `codigo_postal`    | Data             | **sí**        | no              |                                                             |

### Vínculos y auditoría

| Campo                | Tipo          | Reqd          | Read-only en UI | Comentario                                                  |
| -------------------- | ------------- | ------------- | --------------- | ----------------------------------------------------------- |
| `user`               | Link → `User` | no            | no              | `unique` cuando está presente. Misma política que `Socio.user` |
| `socio_vinculado`    | Link → `Socio`| no            | no              | `unique` cuando está presente. Solo poblado si la persona se asocia luego (caso edge) |
| `creado_por`         | Link → `User` | no            | **sí**          | Espejo de `owner`                                            |
| `creado_en`          | Datetime      | no            | **sí**          | Timestamp                                                    |
| `ultima_modificacion_por` | Link → `User` | no       | **sí**          | Última modificación de datos                                 |
| `ultima_modificacion_en`  | Datetime  | no            | **sí**          | Timestamp                                                    |

**Naming:** `autoname` por serie estable `TNS-.{YYYY}.-.####` (ej. `TNS-2026-0042`).
No usar DNI como `name` por la misma razón que en `Socio` (correcciones).

### Documentos adjuntos (alta de menores)

Un vigente por campo; al renovar **pisa** (ver `almacenamiento_documentacion_socios.md`).
No hay ficha médica en el tutor.

| Campo         | Tipo         | Reqd | Comentario                                      |
| ------------- | ------------ | ---- | ----------------------------------------------- |
| `foto_perfil` | Attach Image | no   | Copiado desde `foto_perfil_tutor` al validar    |
| `dni_frente`  | Attach       | no   | Copiado desde `dni_frente_tutor`                |
| `dni_dorso`   | Attach       | no   | Copiado desde `dni_dorso_tutor`                 |

En Desk son opcionales (dato crítico). El portal de alta los exige en la solicitud del menor.

---

## Política de login (espejo de `Socio`)

- `User.username = <dni>`.
- `User.email = <email del Tutor No Socio>` si el email no está tomado por otro `User`.
- Si el email **ya está tomado**, la creación del `Tutor No Socio` con `User` falla
  con `frappe.ValidationError` (mismo criterio que `Socio` adulto).
- **No** se crean emails técnicos sintéticos.
- Login dual por DNI o por número de serie (`TNS-…`) mediante el mismo `auth_hook`
  que resuelve `SOC-…` y `TNS-…`.

---

## Permisos

| Rol              | create | read                      | write | delete |
| ---------------- | ------ | ------------------------- | ----- | ------ |
| `System Manager` | sí     | sí (todos)                | sí    | sí     |
| `Secretaria`     | sí     | sí (todos)                | sí    | no     |
| `Socio`          | no     | sí (solo el tutor de su grupo) | no | no     |
| `Guest`          | no     | no                        | no    | no     |

El rol `Socio` puede ver al `Tutor No Socio` que sea titular de su propio
`Grupo Familiar` (necesario para que el menor o sus familiares lo vean en el
portal). Esto se implementa con `permission_query_conditions` y
`has_permission`.

---

## Scenario: alta de un `Tutor No Socio` requiere mayor de edad

Given un proceso server-side intenta crear un `Tutor No Socio` con
`fecha_nacimiento` que deja a la persona en (hoy − 17 años)
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Tutor No Socio debe ser mayor de 18 años")
And el documento no se persiste.

Given el mismo intento con `fecha_nacimiento` ≤ (hoy − 18 años + 1 día)
When se ejecuta `insert()`
Then la operación tiene éxito
And el documento persiste con `name = "TNS-{YYYY}-####"`.

---

## Scenario: `dni` único entre `Tutor No Socio`

Given existe un `Tutor No Socio` con `dni = "20111111"`
When un proceso intenta crear otro `Tutor No Socio` con el mismo DNI
Then la operación falla con `frappe.DuplicateEntryError`
And no se crea un segundo registro.

> **Nota:** un mismo DNI puede aparecer en `Tutor No Socio` y en `Socio` solo en
> el caso edge en que la persona se asocia después de haber estado registrada
> como tutor. Esa convivencia temporal se permite y se controla con
> `Tutor No Socio.socio_vinculado` (ver scenario abajo).

---

## Scenario: `email` puede repetirse entre `Tutor No Socio` y un `Socio` familiar

Given existe un `Socio` `S_hijo_menor` con `email = "familia@example.com"`
When un proceso crea un `Tutor No Socio` con `email = "familia@example.com"`
y datos consistentes
Then la operación tiene éxito y el `Tutor No Socio` se persiste
And `email` puede coincidir con el de los Socios menores que el tutor maneja.

---

## Scenario: creación con `User` propio cuando el email está libre

Given un `Tutor No Socio` por crear con `dni = "20111111"`,
`email = "papa@example.com"`
And no existe `User` con `name = "papa@example.com"`
And no existe `User` con `username = "20111111"`
When un proceso server-side crea el `Tutor No Socio` y provisiona su `User`
Then se crea un `User` con `name = "papa@example.com"`,
`username = "20111111"`, `enabled = 1`, `user_type = "Website User"`,
rol `Socio` (el rol se llama "Socio" para mantener consistencia con el portal
de membresías; un sprint posterior puede introducir un rol distinto `Tutor`)
And el `Tutor No Socio.user` queda enlazado a ese `User`.

---

## Scenario: creación bloqueada cuando el email está tomado

Given un `Tutor No Socio` por crear con `email = "papa@example.com"`
And ya existe un `User` con `name = "papa@example.com"` (ej. el otro padre/madre)
When un proceso server-side intenta crear el `Tutor No Socio` con `User` propio
Then la operación falla con `frappe.ValidationError`
(mensaje: "El email ya tiene cuenta en el portal; usá un email distinto o
coordiná con Secretaría")
And no se crea ni el `Tutor No Socio` ni un nuevo `User`.

(Para el caso de dos padres/madres del mismo grupo familiar que comparten email
real, en Sprint 0 se acepta que solo uno tenga `User` y el otro figure como
`Tutor No Socio` **sin** `User`. Decisión a refinar en sprints posteriores.)

---

## Scenario: `Tutor No Socio` sin `User` propio es válido

Given un proceso server-side crea un `Tutor No Socio` con `user` vacío
(porque el email coincide con el del otro tutor que ya tiene `User`)
When se ejecuta `insert()`
Then la operación tiene éxito y el documento persiste con `user` vacío
And la gestión del grupo familiar la hace el otro tutor desde su propio portal.

---

## Scenario: login dual con número de serie `TNS-…`

Given un `Tutor No Socio` con `name = "TNS-2026-0007"` y `dni = "20111111"`
enlazado a un `User` con `username = "20111111"`
When el tutor intenta iniciar sesión con `"TNS-2026-0007"`
Then el `auth_hook` reconoce el formato `TNS-{YYYY}-{####}`, busca el
`Tutor No Socio`, obtiene su `dni` y delega al `LoginManager` con el DNI
And la autenticación tiene éxito.

(Mismo patrón que el login dual de `Socio`; el `auth_hook` reconoce ambos
formatos `SOC-…` y `TNS-…`.)

---

## Scenario: el rol `Socio` ve al tutor de su propio grupo

Given un `Grupo Familiar` `G` cuyo `titular` es un `Tutor No Socio` `T`
And un `Socio` `S_hijo` menor, miembro de `G`, con `User` propio `u_hijo`
When `u_hijo` consulta el listado / abre el documento de `T`
Then ve a `T` (un solo registro: el tutor de su grupo)
And **no** ve otros `Tutor No Socio` ajenos.

Given otro `Tutor No Socio` `T2` no relacionado con `G`
When `u_hijo` intenta abrir `T2` directamente por `name`
Then la operación falla con `frappe.PermissionError`.

(Implementación: `permission_query_conditions` (filtra listas) y `has_permission`
(filtra `get_doc` vía REST/portal) registrados en `hooks.py`. Ambos unen el
`Tutor No Socio` con los grupos donde el usuario solicitante es miembro vía
`Socio.user`, o el propio `Tutor No Socio.user`.
**Nota de tests:** la apertura directa por `name` falla con `PermissionError` al
invocar `frappe.has_permission(doctype, "read", doc=name, user=..., throw=True)`,
que es la API que `frappe.client.get` —el endpoint REST que ejerce el portal—
usa bajo el capó. `frappe.get_doc(doctype, name)` server-side no dispara los
hooks en Frappe v15+.)

---

## Scenario: caso edge — `socio_vinculado` se setea si la persona se asocia luego

Given un `Tutor No Socio` `T` con `dni = "20111111"`, `user = "papa@example.com"`,
titular de `Grupo Familiar` `G`
And un proceso server-side crea un `Socio` para esa misma persona con
`dni = "20111111"` (por una nueva Solicitud de Asociación donde ahora sí hace actividad)
When la creación del `Socio` se completa
Then **no** se crea un segundo `User` (se reutiliza el `User` existente: el `Socio`
toma `user = "papa@example.com"`)
And el `Tutor No Socio.socio_vinculado` se setea al `name` del nuevo `Socio`
(idempotente: si ya está poblado, queda igual)
And el `Tutor No Socio` permanece como documento (no se borra) para no romper
referencias dinámicas existentes (titularidad del grupo, tutorías de menores)
And Secretaría tiene la opción de migrar manualmente esas referencias dinámicas
de `Tutor No Socio` → `Socio` en una corrida posterior (fuera de Sprint 0).

---

## Notas de implementación (informativas, no testeables aquí)

- `module` del JSON debe ser `Members`.
- Hooks:
  - `validate()` chequea mayor de edad, DNI único y consistencia de email/User.
  - `before_save` actualiza auditoría (`ultima_modificacion_*`).
  - `after_insert` enlaza `Tutor No Socio.user` si fue creado por el helper de provisión.
- Helper compartido con `Socio`:
  - `members/services/user_provisioning.py::provision_user_for_persona(dni, email, source_doctype, source_name)`
  - Reglas idénticas a las del Socio adulto (no email técnico).
- `auth_hook` `resolve_socio_login` extendido para reconocer `TNS-{YYYY}-{####}`
  además de `SOC-{YYYY}-{####}` y resolver ambos al `username = dni`.
- Tests:
  - `members/doctype/tutor_no_socio/test_tutor_no_socio.py` (mayor de edad, DNI
    único, email duplicado bloquea User, sin User es válido).
  - `tests/test_login_dual.py` (SOC y TNS funcionando contra el mismo
    `auth_hook`).
  - `tests/test_tutor_no_socio_isolation.py` (rol Socio ve solo el tutor de su
    grupo).
