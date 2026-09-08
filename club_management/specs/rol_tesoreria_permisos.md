# Spec: Rol Tesorería y permisos contables

El club necesita un rol **Tesoreria** con lectura contable y acceso al flujo de fondos, separado de **Secretaria**. Secretaría tiene **acceso operativo** a Finanzas (crear/leer facturas de compra, pagos y proveedores, para cargar la provisión de sueldos y egresos) pero **sin** flujo de fondos ni reportes P&L (GF-6).

**Relacionado:** `carga_rapida_ingreso_egreso.md`, `proyeccion_flujo_fondos.md`, `informes_tesoreria_pnl_cashflow.md`

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
And **no** ve el reporte **Proyección de Flujo de Fondos** ni **Ganancias y Pérdidas** ni **Flujo de Efectivo** (roles `Tesoreria` en esos Report).

---

## Scenario: Secretaría puede crear una factura de compra en borrador — GF-6

Given un usuario con rol `Secretaria`
When abre el formulario de `Purchase Invoice`
Then puede crear y guardar en **Borrador** (tiene `create`/`write`, **sin** `submit` ni `cancel`)
And tiene lectura/selección sobre los masters necesarios (Account, Cost Center, Company, Mode of Payment, Supplier)
And sobre **Item** tiene `read`/`select`/`create`/`write` (alta y vínculo en formularios; sin `delete`).

Ver flujo completo en `flujo_egresos_borrador_aprobacion.md`.

---

## Scenario: Secretaría puede seleccionar y crear Items — catálogo operativo

Given un usuario con rol `Secretaria`
When busca un `Item` en un campo Link (factura, grupo/actividad, Club Settings, etc.)
Then el buscador lista ítems (permiso `select`/`read`)
When crea un `Item` nuevo desde Desk
Then puede insertarlo y editarlo (`create`/`write`)
And **no** tiene `delete` sobre Item.

---

## Scenario: Tesorería aprueba/cancela facturas de compra — GF-6

Given un usuario con rol `Tesoreria`
When abre una `Purchase Invoice`
Then tiene permisos totales (`read`/`write`/`create`/`submit`/`cancel`/`delete`) para aprobar o rechazar.

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

## Scenario: workspace de Tesorería con botones navegadores + info debajo — GF-6

Given el workspace `Tesorería`
When se abre en el Desk
Then **no** muestra un bloque de título/header (se eliminó "Tesorería" del contenido)
And arriba muestra **botones navegadores** (shortcuts): Facturas de compra, Pagos y cobros, Plan de cuentas (y Flujo de Fondos solo para `Tesoreria`)
And debajo de los botones carga la información con **quick lists**: "Últimas facturas de compra" (Purchase Invoice) y "Últimos pagos" (Payment Entry).

---

## Scenario: acceso a Tesorería desde la pestaña del sidebar — GF-6

Given la navegación del club (`club_desk_navigation`)
When se renderizan las pestañas
Then aparece la pestaña **"Tesorería"** con el emoji del banco (🏦)
And al hacer clic navega al workspace `Tesorería`.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Constantes / gates | `finance/permissions.py` |
| Patch rol | `patches/v1_0/ensure_role_tesoreria.py` |
| Permisos operativos Secretaría | `finance/setup/secretaria_finance_permissions.py` |
| Patch permisos + workspace Secretaría | `patches/v1_0/add_secretaria_finance_operative_permissions.py` |
| Workspace Tesorería (botones + quick lists) | `finance/workspace/tesoreria/tesoreria.json` |
| Patch re-sync layout | `patches/v1_0/sync_tesoreria_workspace_botones.py` |
| Botón "Ir a Tesorería" (Secretaría) | `public/js/secretaria_workspace_panel.js` |
| App permission | `members/permissions_app.py` |
| Tests | `tests/test_rol_tesoreria.py`, `tests/test_secretaria_finance_permissions.py` |
