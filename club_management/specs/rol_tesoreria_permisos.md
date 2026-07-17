# Spec: Rol Tesorería y permisos contables

El club necesita un rol **Tesoreria** con lectura contable y acceso al flujo de fondos, separado de **Secretaria** (carga operativa sin P&L).

**Relacionado:** `carga_rapida_ingreso_egreso.md`, `proyeccion_flujo_fondos.md`

**Fuera de alcance:** HRMS / liquidación nativa de sueldos (ver backlog).

---

## Scenario: rol Tesoreria existe con Desk

Given el patch de setup financiero se ejecutó
When se consulta el DocType `Role` con name `Tesoreria`
Then existe con `desk_access = 1`.

---

## Scenario: Tesoreria puede leer proyección de flujo

Given un usuario con rol `Tesoreria` (sin System Manager)
When llama a la API de proyección de flujo de fondos
Then obtiene el resumen de liquidez sin error de permisos.

---

## Scenario: Secretaria no accede a proyección de flujo

Given un usuario con rol `Secretaria` (sin Tesoreria ni System Manager)
When llama a la API de proyección de flujo de fondos
Then recibe `PermissionError`.

---

## Scenario: Secretaria no ve reportes P&L en workspace Tesorería

Given el workspace `Tesorería`
When se listan sus roles permitidos
Then incluye `Tesoreria` y `System Manager`
And **no** incluye `Secretaria`.

---

## Scenario: Tesoreria tiene acceso a la app Desk

Given un usuario con solo rol `Tesoreria`
When se evalúa `has_app_permission` de club_management
Then retorna True.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Constantes / gates | `finance/permissions.py` |
| Patch rol | `patches/v1_0/ensure_role_tesoreria.py` |
| App permission | `members/permissions_app.py` |
| Tests | `tests/test_rol_tesoreria.py` |
