# Portal del socio — Perfil (datos personales y foto 4×4)

**Backlog:** extensión del portal autenticado (ver `portal_socio_alcance.md`)
**Relacionado:** `portal_socio_inscripcion.md`, `socio_minimo.md`, `almacenamiento_documentacion_socios.md`, `login_dual.md`

## Decisiones de contrato

- La identidad sale exclusivamente de `frappe.session.user`.
- Ningún endpoint acepta `socio`, `user`, email o número de socio del cliente para elegir qué fila leer o mutar.
- Se exponen **datos personales y de membresía** visibles para el socio, más la **foto de perfil** (`foto_perfil`).
- **No** se exponen adjuntos sensibles (`dni_frente`, `dni_dorso`, `ficha_medica`, `comprobante_jubilado`), auditoría interna, `user`, tutor ni grupo familiar.
- La foto es un `File` **privado**. El browser no llama a Frappe: el BFF de Vercel (`/api/socios/foto`) la obtiene con la sesión y solo si coincide con `foto_perfil` del socio de la sesión.
- El socio **puede actualizar** un subconjunto de datos personales vía `update_perfil_socio`. El rol Desk `Socio` sigue sin `write` en el DocType; la mutación es solo por API whitelisted + `ignore_permissions` acotado a la fila de sesión.
- Renovación de foto 4×4 y “solicitar corrección” de documentos sensibles quedan **fuera** de este corte.

---

## Campos del perfil

| Grupo | Campos | Lectura | Escritura portal |
|-------|--------|---------|------------------|
| Identidad | `numero_socio`, `dni` | sí | **no** (identidad institucional) |
| Identidad | `nombre`, `apellido`, `nacionalidad`, `fecha_nacimiento`, `genero` | sí | **sí** |
| Contacto | `email` | sí | **no** (coincide con `User` de login; cambio vía Secretaría) |
| Contacto | `telefono_fijo`, `telefono_movil` | sí | **sí** |
| Domicilio | `calle`, `numero`, `piso`, `departamento`, `provincia`, `ciudad`, `localidad_barrio`, `codigo_postal` | sí | **sí** |
| Membresía | `estado`, `categoria`, `actividad`, `fecha_ingreso`, `fecha_alta` | sí | **no** |
| Foto | `tiene_foto` | sí | **no** (este corte) |

Whitelist de escritura (`EDITABLE_FIELDS`):
`nombre`, `apellido`, `nacionalidad`, `fecha_nacimiento`, `genero`,
`telefono_fijo`, `telefono_movil`, `calle`, `numero`, `piso`, `departamento`,
`provincia`, `ciudad`, `localidad_barrio`, `codigo_postal`.

La respuesta **no** incluye el `name` interno del DocType `Socio`. Preferir `numero_socio`.

---

## Scenario: socio autenticado ve su perfil

Given un Website User con rol `Socio` y un único `Socio` vinculado
And el socio tiene nombre, DNI, email y foto de perfil
When consulta el perfil del portal
Then recibe sus datos personales y de membresía
And `tiene_foto` es verdadero
And la respuesta no incluye DNI frente/dorso, ficha médica ni campos de auditoría.

---

## Scenario: socio actualiza datos personales propios

Given un Website User con rol `Socio` vinculado a un único `Socio`
When llama `update_perfil_socio` con teléfono móvil y domicilio nuevos
Then persisten solo esos campos en su fila
And el endpoint responde el perfil actualizado
And `dni`, `email`, `estado`, `categoria` y `numero_socio` no cambian.

---

## Scenario: intento de mutar campos bloqueados falla cerrado

Given un socio autenticado
When envía un payload que intenta cambiar `dni`, `email`, `estado` u otro campo no editable a un valor distinto
Then recibe error de validación
And ningún campo del `Socio` queda modificado.

---

## Scenario: no se puede apuntar a otro socio en el update

Given el usuario autenticado A
When llama `update_perfil_socio` pasando `socio` (u otro selector) del socio B
Then la llamada es rechazada (firma o permiso)
And el socio B no se modifica.

---

## Scenario: Guest y roles incorrectos fallan cerrados

Given Guest, un usuario sin rol `Socio`, o un rol `Socio` sin vínculo único
When consulta el perfil, la foto o intenta actualizar
Then recibe error genérico de autenticación o permiso
And no se revela si existe otro socio.

---

## Scenario: aislamiento entre dos socios

Given los usuarios autenticados A y B vinculados a socios distintos
When A consulta o actualiza el perfil
Then solo afecta datos del socio vinculado a A
And no puede obtener la foto de B aunque conozca una URL o nombre de archivo ajeno.

---

## Scenario: foto propia vía proxy

Given un socio autenticado con `foto_perfil` privado
When el BFF solicita la foto con la sesión del socio
Then recibe la imagen (o un 404 limpio si no hay archivo)
And un Guest o sesión ajena no puede leer ese blob.

---

## Scenario: sin foto

Given un socio autenticado sin `foto_perfil`
When consulta el perfil
Then `tiene_foto` es falso
And el proxy de foto responde 404 sin filtrar datos de otro socio.

---

## Fuera de alcance

- Cambiar email o DNI desde el portal (Secretaría).
- Subir o renovar foto 4×4.
- Ver o descargar DNI / ficha médica / comprobante jubilado.
- Carnet digital (spec aparte; puede reutilizar foto más adelante).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/portal_socio_perfil.md` (este archivo) |
| Sesión compartida | `members/services/portal_session.py` |
| API | `members/api/portal_perfil.py` |
| Tests | `members/tests/test_portal_socio_perfil.py` |
| BFF / UI | `pedro-echague-landing-page` — `/socios/perfil`, `/api/socios/perfil`, `/api/socios/foto` |
