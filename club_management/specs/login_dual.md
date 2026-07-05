# Spec: Login dual DNI / email (+ Tutor No Socio) (Sprint 0)

Given/When/Then para el flujo de **inicio de sesión** en el portal del club.

Los socios entran con su **email** o su **DNI** (este último vía `User.username`).
Los **Tutores No Socio** además pueden tipear su número `TNS-{YYYY}-{####}`, que el
`auth_hook` traduce al email asociado.

> **Cambio de diseño (refactor de naming de `Socio`):** el `name` del `Socio` pasó a
> ser un **entero** (número de socio histórico/autoincremental). Por eso **se elimina
> el login por número de socio**: un identificador numérico sería ambiguo con el DNI
> (también numérico y usado como `User.username`). El hook ya **no** reescribe
> identificadores de `Socio`; sí conserva la traducción de `Tutor No Socio`
> (`TNS-…`), cuyo naming no cambió.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`
**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

**Ubicación del código:** `club_management/members/auth/dual_login.py`
**Hook a registrar:** `auth_hooks` en `club_management/hooks.py`
**Módulo Frappe:** `Members`

---

## Objetivo y alcance

Sprint 0 entrega:

- Función `resolve_login_user(login_manager)` que se registra en `auth_hooks` y
  reescribe `login_manager.user` cuando el usuario tipea un identificador
  alternativo válido:
  - `TNS-YYYY-####` → resuelve a `Tutor No Socio.user` (email).
  - `DNI` numérico → **no se toca**: se delega al login nativo de Frappe, que
    ya soporta `User.username` (con `System Settings.allow_login_using_user_name = 1`)
    y nuestros servicios `provision_user_for_socio` /
    `provision_user_for_tutor_no_socio` setean `User.username = DNI`.
  - Número de socio (entero, p. ej. `"1500"`) → **no se toca**: queda como un
    identificador numérico que Frappe procesa por `username`/email; el login por
    número de socio fue eliminado en el refactor de naming.
  - Email u otro string → **no se toca**: comportamiento nativo de Frappe.

Quedan **fuera** de Sprint 0:

- Cambiar la apariencia de la pantalla de login (texto, placeholders).
- Two-factor authentication.
- Resolución por número de teléfono.

---

## Reglas de resolución

| Input del usuario               | Acción                                                            |
| ------------------------------- | ----------------------------------------------------------------- |
| `""` o `None`                   | No hacer nada.                                                    |
| Match `^TNS-\d{4}-\d{4,}$`      | Buscar `Tutor No Socio` por `name`; si existe y `.user` está poblado, setear `login_manager.user = Tutor No Socio.user`. |
| Número de socio entero (`"1500"`) | No hacer nada (login por número de socio eliminado; Frappe maneja email y `User.username`). |
| Otro string                     | No hacer nada (Frappe maneja email y `User.username`).            |
| Tutor inexistente               | No hacer nada (Frappe fallará el login con mensaje estándar).     |
| Tutor sin `user`                | No hacer nada (Frappe fallará el login con mensaje estándar).     |

La función **nunca debe lanzar excepciones** sobre el `LoginManager`: el peor
caso aceptable es no resolver y dejar que Frappe falle el login con su error
estándar de credenciales inválidas.

---

## Permisos y seguridad

- La función llama `frappe.db.get_value(...)` con `ignore_permissions` implícito
  (`frappe.db.*` no aplica permisos). Esto es **deliberado**: durante el login
  el usuario todavía es `Guest`, y necesitamos resolver el email **antes** de
  validar la contraseña. La función no devuelve el email al cliente: sólo
  actualiza `login_manager.user` para que Frappe siga con la validación normal.
- Si el `SOC-` o `TNS-` no existe, **no** se debe loggear nada que distinga
  "no existe" de "contraseña inválida" en respuesta al cliente, para no filtrar
  qué números están dados de alta. Frappe ya devuelve el mismo error
  `Incorrect User or Password` en ambos casos, lo que cubre esto.

---

## Escenarios (Given/When/Then)

### Escenario 1: Login con número de Socio (entero) NO se intercepta

- **Given** un `Socio` con `name = "1500"`, `email = "ana@example.com"`,
  `dni = "30123456"` y `user = "ana@example.com"` (provision_user previo).
- **When** un cliente intenta iniciar sesión con `usr = "1500"`.
- **Then** `resolve_login_user(login_manager)` **no** modifica `login_manager.user`
  (queda `"1500"`); el login por número de socio fue eliminado en el refactor de
  naming. El socio entra con su email o su DNI.

### Escenario 2: Login con número de Tutor No Socio resuelve al email

- **Given** un `Tutor No Socio` `TNS-2026-0001` con `email = "juan@example.com"`,
  `dni = "20111111"` y `user = "juan@example.com"`.
- **When** `usr = "TNS-2026-0001"`.
- **Then** `login_manager.user = "juan@example.com"`.

### Escenario 3: Login con email se delega a Frappe

- **Given** mismos datos del Escenario 1.
- **When** `usr = "ana@example.com"`.
- **Then** `login_manager.user` queda **sin tocar** (sigue siendo `"ana@example.com"`).

### Escenario 4: Login con DNI se delega a Frappe

- **Given** mismos datos del Escenario 1; el `User.username = "30123456"`.
- **When** `usr = "30123456"`.
- **Then** `login_manager.user` queda **sin tocar**. El login nativo de Frappe
  resuelve `User` por `username` con `allow_login_using_user_name = 1`.

### Escenario 5: Número de Socio inexistente no rompe el login

- **Given** no existe ningún `Socio` con `name = "999999"`.
- **When** `usr = "999999"`.
- **Then** `login_manager.user` queda en `"999999"`; Frappe responde
  con error estándar de credenciales inválidas.

### Escenario 6: Socio sin `User` no se resuelve

- **Given** un `Socio` `name = "1700"` (menor sin `User`, `Socio.user IS NULL`).
- **When** `usr = "1700"`.
- **Then** `login_manager.user` queda en `"1700"`; el hook no lo toca y Frappe
  responde error de credenciales (correcto: ese socio no tiene login propio).

### Escenario 7: Identificador vacío no rompe el login

- **Given** `login_manager.user = ""` o `None`.
- **When** se invoca `resolve_login_user(login_manager)`.
- **Then** no se modifica nada y no se lanza excepción.

### Escenario 8: Formato `TNS-` similar pero inválido no resuelve

- **Given** `usr = "TNS-2026-1"` (faltan dígitos) o `"TNS-26-0001"`
  (año con 2 dígitos).
- **When** se invoca el hook.
- **Then** `login_manager.user` queda sin tocar (Frappe lo tratará como email
  inválido o usuario inexistente).

---

## Registro en `hooks.py`

```python
auth_hooks = [
    "club_management.members.auth.dual_login.resolve_login_user",
]
```

---

## Tests asociados

`club_management/members/tests/test_login_dual.py`:

- Usa un `FakeLoginManager` con sólo el atributo `user`, no ejerce el flujo
  HTTP/contraseña: prueba **únicamente** que `resolve_login_user` resuelve el
  campo correctamente para cada escenario.
- Cubre los 8 escenarios listados arriba.
- Hereda de `MembersTestCase` para aislar registros creados por SAVEPOINT.
