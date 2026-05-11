# Spec: Login dual DNI / Número de Socio (Sprint 0)

Given/When/Then para el flujo de **inicio de sesión** en el portal del club.

Los socios y tutores no recuerdan su email registrado, pero sí su **DNI** o su
**número de socio**. Esta spec describe cómo se acepta cualquiera de esos tres
identificadores en el campo *Login Id* del portal, sin tocar el `LoginManager`
nativo de Frappe (todo se resuelve vía `auth_hooks`).

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
  - `SOC-YYYY-####` → resuelve a `Socio.user` (email).
  - `TNS-YYYY-####` → resuelve a `Tutor No Socio.user` (email).
  - `DNI` numérico → **no se toca**: se delega al login nativo de Frappe, que
    ya soporta `User.username` (con `System Settings.allow_login_using_user_name = 1`)
    y nuestros servicios `provision_user_for_socio` /
    `provision_user_for_tutor_no_socio` setean `User.username = DNI`.
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
| Match `^SOC-\d{4}-\d{4,}$`      | Buscar `Socio` por `name`; si existe y `Socio.user` está poblado, setear `login_manager.user = Socio.user`. |
| Match `^TNS-\d{4}-\d{4,}$`      | Idem con `Tutor No Socio`.                                        |
| Otro string                     | No hacer nada (Frappe maneja email y `User.username`).            |
| Socio/Tutor inexistente         | No hacer nada (Frappe fallará el login con mensaje estándar).     |
| Socio/Tutor sin `user`          | No hacer nada (Frappe fallará el login con mensaje estándar).     |

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

### Escenario 1: Login con número de Socio resuelve al email

- **Given** un `Socio` `SOC-2026-0001` con `email = "ana@example.com"`,
  `dni = "30123456"` y `user = "ana@example.com"` (provision_user previo).
- **When** un cliente intenta iniciar sesión con `usr = "SOC-2026-0001"`.
- **Then** `resolve_login_user(login_manager)` setea
  `login_manager.user = "ana@example.com"` y Frappe valida la contraseña contra
  ese `User`.

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

- **Given** no existe ningún `Socio` con `name = "SOC-2099-9999"`.
- **When** `usr = "SOC-2099-9999"`.
- **Then** `login_manager.user` queda en `"SOC-2099-9999"`; Frappe responde
  con error estándar de credenciales inválidas.

### Escenario 6: Socio sin `User` no se resuelve

- **Given** un `Socio` `SOC-2026-0099` (menor sin `User`, `Socio.user IS NULL`).
- **When** `usr = "SOC-2026-0099"`.
- **Then** `login_manager.user` queda en `"SOC-2026-0099"`; Frappe responde
  error de credenciales (correcto: ese socio no tiene login propio).

### Escenario 7: Identificador vacío no rompe el login

- **Given** `login_manager.user = ""` o `None`.
- **When** se invoca `resolve_login_user(login_manager)`.
- **Then** no se modifica nada y no se lanza excepción.

### Escenario 8: Formato similar pero inválido no resuelve

- **Given** `usr = "SOC-2026-1"` (faltan dígitos) o `"SOC-26-0001"`
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
