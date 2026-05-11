# Spec: Grupo Familiar mínimo (Sprint 0)

Given/When/Then para el **DocType `Grupo Familiar`** y la **Child Table
`Miembro de Grupo Familiar`**. Este DocType es prerrequisito de
`socio_minimo.md` cuando `Socio.categoria = "Menor"`, y habilita en
sprints posteriores el descuento por hermanos descrito en
`socios_categoria_validacion.md`.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`
**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

**Ubicación de los DocTypes:**

- `club_management/members/doctype/grupo_familiar/`
- `club_management/members/doctype/miembro_de_grupo_familiar/` (child de Socios miembros)
- `club_management/members/doctype/titular_de_grupo_familiar/` (child de titulares — admite cotitulares)

**Módulo Frappe:** `Members`

---

## Objetivo y alcance

Sprint 0 entrega:

- DocType estándar `Grupo Familiar` con titular obligatorio mayor de edad.
- Child Table `Miembro de Grupo Familiar` con `socio` (link único entre grupos
  activos) y `rol`.
- Reglas de invariante: un `Socio` no puede estar en dos grupos activos a la vez;
  todo `Socio` con `categoria = "Menor"` debe estar en un grupo y tener al menos un
  miembro mayor de edad como `tutor` referenciable.
- Permisos: `Secretaria` gestiona; `Socio` ve solo su propio grupo.

Quedan **fuera** de Sprint 0:

- Descuento automático por hermanos en facturación (cubierto por
  `socios_categoria_validacion.md`).
- Asistencia compartida del tutor a actividades de menores (sprint posterior).
- Histórico de pertenencia (entrada/salida) más allá de los campos `desde`/`hasta`
  del child; no se implementan reportes históricos en Sprint 0.

---

## Campos propuestos — `Grupo Familiar` (DocType estándar)

### Datos del grupo

| Campo                  | Tipo                                  | Reqd          | Read-only en UI | Comentario                                              |
| ---------------------- | ------------------------------------- | ------------- | --------------- | ------------------------------------------------------- |
| `nombre_grupo`         | Data                                  | sí            | no              | Display name, ej. "Familia Pérez Gómez"                 |
| `apellido_principal`   | Data                                  | sí            | no              | Apellido(s) usual(es) del grupo (auditoría/búsqueda)    |
| `domicilio_principal`  | Small Text                            | no            | no              | Domicilio de referencia del grupo                       |

### Titulares (cotitulares, child table polimórfica)

Un grupo familiar puede tener uno o más **cotitulares**: típicamente padre y
madre, o un tutor legal solo, o ambos padres además de un abuelo titular legal.
Cada titular puede ser un `Socio` (si el adulto también realiza actividad) o
un `Tutor No Socio` (si solo gestiona y no se asocia).

Se modela con una child table `titulares` con filas polimórficas (Dynamic Link).

| Campo       | Tipo                                    | Reqd          | Read-only en UI | Comentario                                                  |
| ----------- | --------------------------------------- | ------------- | --------------- | ----------------------------------------------------------- |
| `titulares` | Table → `Titular de Grupo Familiar`     | sí (≥ 1 fila) | no              | Al menos un titular activo y exactamente uno principal      |

> Acceso rápido: el controlador expone un método
> `grupo.get_titular_principal() -> (tipo, name)` que devuelve la fila activa
> con `es_principal = 1`. No se persiste un campo top-level "titular_principal"
> para evitar dos fuentes de verdad.

Restricción adicional sobre la child table:

- **Exactamente** una fila activa con `es_principal = 1` y `hasta` vacío.
- Cada `(tipo_titular, titular)` distinta entre filas activas (sin duplicados
  dentro del mismo grupo).
- La misma `(tipo_titular, titular)` no puede aparecer como titular activo en
  otro `Grupo Familiar` distinto (una persona no encabeza dos grupos a la vez).
- Todos los titulares activos deben ser mayores de 18 años a la fecha actual.

### Miembros

| Campo      | Tipo                                  | Reqd          | Read-only en UI | Comentario                                                  |
| ---------- | ------------------------------------- | ------------- | --------------- | ----------------------------------------------------------- |
| `miembros` | Table → `Miembro de Grupo Familiar`   | depende       | no              | Child table de **Socios miembros** del grupo. Cada titular `tipo = "Socio"` es automáticamente miembro; los titulares `Tutor No Socio` **no** aparecen aquí. La tabla puede estar vacía si todos los titulares son `Tutor No Socio` y los Socios menores aún no se cargaron. |

### Auditoría (todos `read-only` en UI; setean server-side)

| Campo                | Tipo          | Reqd | Comentario                                              |
| -------------------- | ------------- | ---- | ------------------------------------------------------- |
| `creado_por`         | Link → `User` | no   | Quién creó el grupo (espejo explícito de `owner`)       |
| `creado_en`          | Datetime      | no   | Timestamp de creación                                   |
| `ultima_modificacion_por` | Link → `User` | no | Última modificación de miembros / titular              |
| `ultima_modificacion_en` | Datetime  | no   | Timestamp                                               |

**Naming:** `autoname` por serie estable `GF-.{YYYY}.-.####` (ej. `GF-2026-0017`).

---

## Campos propuestos — `Miembro de Grupo Familiar` (Child Table, `istable: 1`)

| Campo   | Tipo                | Reqd | `in_list_view` | Comentario                                                |
| ------- | ------------------- | ---- | -------------- | --------------------------------------------------------- |
| `socio` | Link → `Socio`      | sí   | sí             | Único entre grupos activos                                |
| `rol`   | Select              | sí   | sí             | `Titular` / `Cónyuge` / `Hijo` / `Padre` / `Madre` / `Otro` |
| `desde` | Date                | no   | no             | Fecha de incorporación al grupo                           |
| `hasta` | Date                | no   | no             | Fecha de salida; si está vacío, el vínculo está vigente   |
| `notas` | Small Text          | no   | no             | Observación libre                                         |

Convención: un miembro está **activo** si `hasta` está vacío o es posterior a la
fecha de consulta.

---

## Campos propuestos — `Titular de Grupo Familiar` (Child Table, `istable: 1`)

| Campo            | Tipo                                            | Reqd | `in_list_view` | Comentario                                                                  |
| ---------------- | ----------------------------------------------- | ---- | -------------- | --------------------------------------------------------------------------- |
| `tipo_titular`   | Select                                          | sí   | sí             | `"Socio"` / `"Tutor No Socio"`                                              |
| `titular`        | Dynamic Link (`options = tipo_titular`)         | sí   | sí             | Apunta al `Socio` o `Tutor No Socio` correspondiente                        |
| `es_principal`   | Check                                           | sí   | sí             | Exactamente una fila activa por grupo                                       |
| `rol`            | Select                                          | sí   | sí             | `"Padre"` / `"Madre"` / `"Tutor Legal"` / `"Cotitular"` / `"Otro"`           |
| `desde`          | Date                                            | no   | no             | Fecha de inicio de la titularidad                                           |
| `hasta`          | Date                                            | no   | no             | Si está vacío, la titularidad está vigente                                  |
| `notas`          | Small Text                                      | no   | no             | Observación libre (ej. "tutor legal por sentencia 2021")                    |

Convención: un titular está **activo** si `hasta` está vacío o es posterior a la
fecha de consulta.

---

## Permisos

| Rol              | create | read                 | write | delete |
| ---------------- | ------ | -------------------- | ----- | ------ |
| `System Manager` | sí     | sí (todos los grupos) | sí    | sí     |
| `Secretaria`     | sí     | sí (todos los grupos) | sí    | no     |
| `Socio`          | no     | sí (solo su grupo)   | no    | no     |
| `Guest`          | no     | no                    | no    | no     |

El rol `Socio` ve su propio grupo y los datos de los demás miembros del mismo grupo
(necesario para el portal y para que el tutor gestione a sus menores).

---

## Scenario: alta con un titular `Socio` requiere mayor de edad

Given un proceso server-side intenta crear un `Grupo Familiar` con `titulares`:
una fila `{tipo_titular: "Socio", titular: <Socio_S>, es_principal: 1, rol: "Titular"}`
donde `S.fecha_nacimiento` deja a `S` en (hoy − 15 años)
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Titular debe ser mayor de 18 años")
And el grupo no se persiste.

Given el mismo intento con `titular = <Socio_T>` mayor de 18 años
When se ejecuta `insert()`
Then la operación tiene éxito
And el grupo persiste con `name = "GF-{YYYY}-####"` y una fila titular principal
con `(tipo_titular = "Socio", titular = T)`.

---

## Scenario: alta con titular `Tutor No Socio` (caso padre que asocia menores)

Given un `Tutor No Socio` `T_padre` mayor de 18 años con `dni = "20111111"`
And dos solicitudes de menores ya creadas (aún no validadas) que lo declaran
como tutor
When un proceso server-side crea un `Grupo Familiar` con `titulares`:
una fila `{tipo_titular: "Tutor No Socio", titular: T_padre, es_principal: 1, rol: "Padre"}`
And `miembros` vacío
Then la operación tiene éxito
And el grupo persiste con `name = "GF-{YYYY}-####"` y `get_titular_principal()`
devuelve `("Tutor No Socio", T_padre.name)`
And la child table `miembros` queda vacía (los menores se agregarán al validar
sus respectivas solicitudes).

---

## Scenario: alta con dos cotitulares (padre y madre)

Given dos `Tutor No Socio` `T_padre` y `T_madre`, ambos mayores de 18, con
`dni` distinto cada uno
When un proceso crea un `Grupo Familiar` con `titulares`:
- `{tipo_titular: "Tutor No Socio", titular: T_padre, es_principal: 1, rol: "Padre"}`
- `{tipo_titular: "Tutor No Socio", titular: T_madre, es_principal: 0, rol: "Madre"}`
Then la operación tiene éxito
And `get_titular_principal()` devuelve `("Tutor No Socio", T_padre.name)`
And ambos cotitulares figuran activos (`hasta` vacío)
And el sistema acepta combinar libremente `tipo_titular` (uno Socio y otro
Tutor No Socio en el mismo grupo está permitido).

---

## Scenario: exactamente un titular activo principal por grupo

Given un intento de crear un `Grupo Familiar` con dos filas activas marcadas
`es_principal = 1`
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Debe haber exactamente un titular principal activo")
And el grupo no se persiste.

Given un intento con cero filas `es_principal = 1` (todas en 0)
When se ejecuta `insert()`
Then la operación falla con el mismo mensaje y el grupo no se persiste.

Given un grupo válido con un principal y dos cotitulares no principales
And la fila principal se cierra (`hasta = hoy`) sin marcar otra como principal
When se ejecuta `save()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Cerrar el titular principal exige promover un cotitular activo a principal")
And el `save` no persiste.

---

## Scenario: cualquier titular `Socio` queda automáticamente como miembro

Given un proceso crea un `Grupo Familiar` con `titulares`:
- `{tipo_titular: "Socio", titular: S_padre, es_principal: 1, rol: "Padre"}`
- `{tipo_titular: "Socio", titular: S_madre, es_principal: 0, rol: "Madre"}`
And `miembros` vacío
When se ejecuta `insert()`
Then la operación tiene éxito
And `miembros` contiene filas para `S_padre` y `S_madre` con `rol = "Titular"`,
`desde = hoy`, `hasta` vacío (auto-agregadas por `before_insert`).
And los Tutor No Socio nunca se agregan a `miembros`.

---

## Scenario: titulares `Tutor No Socio` no aparecen en `miembros`

Given un proceso crea un `Grupo Familiar` con `titulares`:
una fila `{tipo_titular: "Tutor No Socio", titular: T_padre, es_principal: 1, rol: "Padre"}`
And `miembros` vacío
When se ejecuta `insert()`
Then la operación tiene éxito y `miembros` permanece vacío.

---

## Scenario: cualquier titular activo debe ser mayor de 18

Given un proceso intenta crear un `Grupo Familiar` con `titulares`:
- `{tipo_titular: "Socio", titular: S_adulto, es_principal: 1, rol: "Padre"}` (válido)
- `{tipo_titular: "Tutor No Socio", titular: T_x, es_principal: 0, rol: "Otro"}`
  donde `T_x` tiene `fecha_nacimiento` que lo deja en (hoy − 17 años)
When se ejecuta `insert()`
Then la operación falla con `frappe.ValidationError`
(mensaje: "Titular debe ser mayor de 18 años")
And el grupo no se persiste.

(El controlador de `Tutor No Socio` ya bloquea < 18 al crear; el grupo revalida
por seguridad ante ediciones manuales.)

---

## Scenario: un `Socio` no puede estar en dos grupos activos a la vez

Given un `Socio` `S` ya activo (miembro con `hasta` vacío) en `Grupo Familiar` `G1`
When un proceso intenta agregar a `S` como miembro activo en `Grupo Familiar` `G2`
(`hasta` vacío)
Then la operación falla con `frappe.ValidationError`
(mensaje: "Socio ya pertenece a otro Grupo Familiar")
And `G2` no persiste la nueva fila.

Given `S` con su vínculo en `G1` cerrado (`hasta` = ayer)
When un proceso lo agrega como miembro activo de `G2` (`hasta` vacío)
Then la operación tiene éxito (el vínculo de `G1` ya no es activo).

---

## Scenario: una persona no encabeza dos grupos activos a la vez

Given un `Tutor No Socio` `T` ya es titular activo (cualquier `es_principal`) de
`Grupo Familiar` `G1`
When un proceso intenta crear `Grupo Familiar` `G2` con `titulares` incluyendo
una fila activa `{tipo_titular: "Tutor No Socio", titular: T, ...}`
Then la operación falla con `frappe.ValidationError`
(mensaje: "La persona ya es titular activa en otro Grupo Familiar")
And `G2` no se persiste.

(Mismo principio se aplica si la fila tiene `tipo_titular = "Socio"` y el
`Socio` ya es titular activo de otro grupo.)

---

## Scenario: cambio de titular dentro del mismo grupo (Socio → Socio)

Given un `Grupo Familiar` `G` con un único titular `(Socio, T)` principal
When un proceso intenta cambiar el principal por `T2` sin agregar `T2` como
miembro
Then la operación falla con `frappe.ValidationError`
(mensaje: "Nuevo titular Socio debe pertenecer al grupo como miembro con `rol = Titular`")
And el cambio no persiste.

Given el cambio se hace cerrando la fila de titular de `T` (`hasta = hoy`,
`es_principal = 0`) y agregando una nueva fila
`{tipo_titular: "Socio", titular: T2, es_principal: 1, rol: "Titular",
desde: hoy}`
And la child table `miembros` también se ajusta cerrando a `T` y agregando a `T2`
When se ejecuta el cambio
Then la operación tiene éxito y `get_titular_principal()` devuelve `("Socio", T2.name)`.

---

## Scenario: cambio de titular cruzado (Tutor No Socio → Socio)

Given un `Grupo Familiar` `G` con titular principal `(Tutor No Socio, T_padre)`
y miembros = [`S_hijo1`, `S_hijo2`]
And el `Tutor No Socio` `T_padre` se asocia en una solicitud posterior y se
crea un `Socio` `S_padre` con `dni = T_padre.dni`
When `Secretaria` ejecuta el cambio del principal a `(Socio, S_padre)`
(cerrando la fila vieja y agregando la nueva como `es_principal = 1`)
Then la operación tiene éxito siempre que `S_padre` quede como miembro del
grupo con `rol = "Titular"` (auto-agregado por `before_save`)
And `Tutor No Socio.socio_vinculado = S_padre.name` (idempotente)
And el grupo conserva su `name = "GF-…"` y a los hijos como miembros.

---

## Scenario: borrar un grupo está prohibido para `Secretaria`

Given un usuario con rol `Secretaria` y un `Grupo Familiar` existente
When intenta borrar el documento
Then la operación falla con `frappe.PermissionError`.

Given el mismo grupo
And un usuario con rol `System Manager`
When intenta borrarlo
Then la operación tiene éxito (caso administrativo / cancelación).

---

## Scenario: el rol `Socio` ve solo su propio grupo y los miembros del mismo

Given dos `Grupo Familiar` `G1` y `G2` con miembros distintos
And un `User` con rol `Socio` enlazado a un `Socio` que es miembro de `G1`
When ese usuario consulta el listado de `Grupo Familiar`
Then ve solo `G1` (cero filas para `G2`)
And puede abrir `G1` y ver los demás miembros (nombre, rol, desde/hasta)
And puede ver al `titular` de `G1` (sea `Socio` u `Tutor No Socio`)
And la apertura directa de `G2` por `name` falla con `frappe.PermissionError`.

(Implementación: `permission_query_conditions` (filtra listas) y `has_permission`
(filtra `get_doc` vía REST/portal) registrados en `hooks.py`, consultando los
`socio` de la child table `miembros` y los `titular` activos con
`tipo_titular = "Tutor No Socio"` en función del `User` del solicitante.
**Nota de tests:** la apertura directa por `name` falla con `PermissionError` al
invocar `frappe.has_permission(doctype, "read", doc=name, user=..., throw=True)`,
que es la API que `frappe.client.get` —el endpoint REST que ejerce el portal—
usa bajo el capó. `frappe.get_doc(doctype, name)` server-side no dispara los
hooks en Frappe v15+.)

---

## Scenario: un `Socio` menor de edad debe tener un tutor consistente con el grupo

Given un `Socio` `S_menor` con `categoria = "Menor"`, `grupo_familiar = G`,
`tipo_tutor` ∈ `{"Socio", "Tutor No Socio"}` y `tutor` apuntando a la persona
correspondiente
When se ejecuta `S_menor.insert()` o `save()`
Then el `validate()` de `Socio` verifica que la persona referenciada por
`(tipo_tutor, tutor)`:
  - tiene `fecha_nacimiento` que la hace mayor de 18 años, y
  - figura como **titular activo** de `G` con esa misma `(tipo_titular, titular)`
    (puede ser principal o cotitular; basta con que esté en `G.titulares` con
    `hasta` vacío)
And si **alguna** condición no se cumple, la operación falla con
`frappe.ValidationError` (con mensaje específico de la condición violada)
And el menor no persiste.

(Antes este Scenario distinguía dos ramas según el tipo de tutor; ahora se
unifica porque tanto Socio como Tutor No Socio aparecen en `G.titulares`.)

(Este Scenario duplica una invariante del menor; vive aquí porque la regla **cruza**
los DocTypes `Socio`, `Grupo Familiar` y `Tutor No Socio` y conviene tener una
prueba dedicada.)

---

## Scenario: las modificaciones registran auditoría

Given un `Grupo Familiar` `G` existente, con `ultima_modificacion_por` vacío
And un proceso server-side ejecuta como `Secretaria` "ana@example.com" un cambio
en `G.miembros` (alta de un nuevo miembro)
When se persiste el cambio
Then `G.ultima_modificacion_por` = `"ana@example.com"`
And `G.ultima_modificacion_en` ≈ ahora (tolerancia ≤ 5s)
And `G.creado_por` y `G.creado_en` permanecen iguales (auditoría de creación es
inmutable después del primer `insert()`).

---

## Notas de implementación (informativas, no testeables aquí)

- `module` del JSON debe ser `Members` para los tres DocTypes
  (`Grupo Familiar`, `Miembro de Grupo Familiar`, `Titular de Grupo Familiar`).
- Hooks de validación en `Grupo Familiar.validate()`:
  - Cada titular activo (`hasta` vacío) mayor de 18 años (sea `Socio` o `Tutor No Socio`).
  - Exactamente una fila activa con `es_principal = 1`.
  - Unicidad de `(tipo_titular, titular)` dentro del grupo (sin duplicados entre filas activas).
  - Unicidad cross-grupo: ninguna `(tipo_titular, titular)` activa está activa también en otro grupo.
  - `before_insert` / `before_save`: por cada titular activo con `tipo_titular = "Socio"`,
    sincronizar la presencia en `miembros` con `rol = "Titular"` (idempotente).
- Hook cross-DocType en `Socio.validate()`: cuando `categoria = "Menor"`,
  la persona referenciada por `(tipo_tutor, tutor)` debe figurar como titular
  activo (cualquier `es_principal`) del `grupo_familiar` declarado.
- Permisos del `Grupo Familiar` (`permission_query_conditions`, SQL PostgreSQL v14):
  ```sql
  EXISTS (
    SELECT 1 FROM "tabMiembro de Grupo Familiar" m
    WHERE m.parent = "tabGrupo Familiar".name
      AND m.socio IN (SELECT name FROM "tabSocio" WHERE "user" = %(user)s)
  )
  OR EXISTS (
    SELECT 1 FROM "tabTitular de Grupo Familiar" t
    WHERE t.parent = "tabGrupo Familiar".name
      AND t.tipo_titular = 'Tutor No Socio'
      AND t.titular IN (SELECT name FROM "tabTutor No Socio" WHERE "user" = %(user)s)
  )
  ```
- Tests:
  - `members/doctype/grupo_familiar/test_grupo_familiar.py`
    → un titular Socio, un titular Tutor No Socio, cotitulares (padre + madre),
    exactamente un principal activo, unicidad por persona, cambio de titular,
    auto-incorporación de Socio titular como miembro.
  - `tests/test_socio_familia.py`
    → invariante menor↔tutor↔grupo con ambos tipos de tutor; tutor cotitular
    (no principal) válido para un menor.
  - `tests/test_grupo_familiar_isolation.py`
    → `permission_query_conditions` para rol Socio (vía `miembros`) y
    para Tutor No Socio con `User` (vía `titulares`).
