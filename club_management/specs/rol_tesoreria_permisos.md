# Spec: Rol Tesorería y permisos contables

El club necesita un rol **Tesoreria** con lectura contable y acceso al flujo de fondos, separado de **Secretaria**. Secretaría tiene **acceso operativo** a Finanzas (crear/leer facturas de compra, pagos y proveedores, para cargar la provisión de sueldos y egresos) pero **sin** flujo de fondos ni reportes P&L (GF-6).

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

## Scenario: Secretaría accede al workspace de Finanzas (operativo) — GF-6

Given el workspace `Tesorería`
When se listan sus roles permitidos
Then incluye `Tesoreria`, `Secretaria` y `System Manager`.

---

## Scenario: Secretaría ve solo accesos operativos (sin flujo/P&L) — GF-6

Given un usuario con rol `Secretaria` (sin `Tesoreria`)
When abre el workspace de Finanzas
Then ve los accesos a **Facturas de compra** y **Pagos y cobros**
And **no** ve el reporte **Proyección de Flujo de Fondos** (el link se filtra por permiso, ya que el reporte requiere rol `Tesoreria`).

---

## Scenario: Secretaría puede crear una factura de compra — GF-6

Given un usuario con rol `Secretaria`
When abre el formulario de `Purchase Invoice`
Then puede crear y guardar (tiene `create`/`write`/`submit` operativo)
And tiene lectura sobre los masters necesarios (Item, Account, Cost Center, Company, Mode of Payment, Supplier).

---

## Scenario: el módulo Finanzas es visible para los roles financieros — GF-6

Given que Frappe solo muestra un workspace si su **módulo** está en los módulos permitidos del usuario
And que los módulos permitidos se derivan de los DocTypes que el usuario puede leer
When el módulo `Finance` no contiene ningún DocType propio
Then ni `Tesoreria` ni `Secretaria` verían el workspace (bug: solo Administrator lo veía).

## Scenario: DocType `Finance Settings` habilita el módulo — GF-6

Given el DocType Single `Finance Settings` en el módulo `Finance`
And permisos de lectura para `Tesoreria` y `Secretaria`
When un usuario con esos roles abre el Desk
Then `Finance` está en sus módulos permitidos
And el workspace de Tesorería/Finanzas se muestra.

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
| Permisos operativos Secretaría | `finance/setup/secretaria_finance_permissions.py` |
| Patch permisos + workspace Secretaría | `patches/v1_0/add_secretaria_finance_operative_permissions.py` |
| App permission | `members/permissions_app.py` |
| Tests | `tests/test_rol_tesoreria.py`, `tests/test_secretaria_finance_permissions.py` |
