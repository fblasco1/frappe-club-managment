# Spec: Panel operativo de Tesorería (GF-6)

El workspace **Tesorería** deja de usar los widgets nativos y pasa a un **panel custom** (JS + CSS + API), consistente con los paneles de Secretaría y Actividades. Muestra los accesos como **botones de acción alineados a la izquierda** y, debajo, **listas** con las operaciones del club incluyendo **plan de cuenta** y **centro de costo**.

**Relacionado:** `rol_tesoreria_permisos.md`, `carga_rapida_ingreso_egreso.md`

## Contexto de dominio (ERPNext)

- **Factura de Compra** (`Purchase Invoice`): único DocType de egresos del club. Se carga en **Borrador** (`docstatus = 0`) y Tesorería la **Presenta** (`docstatus = 1`). Ver `flujo_egresos_borrador_aprobacion.md`.
- **Cobro** (`Payment Entry`, `payment_type = Receive`): dinero recibido por el club.

> Nota: se **eliminó** el uso de `Purchase Order` en el club.

---

## Scenario: acceso al panel restringido a roles financieros

Given un usuario **sin** rol `Tesoreria`/`Secretaria`/`System Manager`
When llama a la API del panel de Tesorería
Then recibe `PermissionError`.

Given un usuario con rol `Secretaria` **o** `Tesoreria`
When llama a la API del panel
Then obtiene los datos sin error.

---

## Scenario: tarjeta de liquidez a 5 días (día 1)

Given un usuario con acceso al panel (`Tesoreria` o `Secretaria`)
When se arma el panel
Then incluye un resumen `liquidez` con `liquidez_proyectada` y `gastos_proyectados_pendientes`
And la ventana es de **5** días (`calcular_proyeccion_flujo_fondos`)
And el cálculo se invoca con `skip_permission_check=True` **después** del gate `ensure_finance_panel_access` (Secretaría ya ve borradores; no se exige rol Tesoreria para el número)
And si ERPNext no está instalado, `liquidez` es `null` y el panel no falla
And el workspace muestra esas cifras arriba de las listas, sin abrir el Script Report.

---

## Scenario: botones de acción a la izquierda

Given el panel de Tesorería
When se renderiza
Then muestra, alineado a la izquierda, el botón **"Crear Factura de Compra"**
And abre un nuevo `Purchase Invoice`.

---

## Scenario: lista PAGOS PENDIENTES (facturas en borrador)

Given facturas de compra en **Borrador** (`docstatus = 0`)
When se arma el panel
Then se listan esas facturas bajo **PAGOS PENDIENTES**
And cada fila incluye **proveedor**, **importe**, **fecha de vencimiento**, **plan de cuenta** (expense_account de los ítems) y **centro de costo** (cost_center de los ítems)
And al hacer clic se abre el formulario para que Tesorería la Presente (apruebe).

---

## Scenario: lista de facturas de compra pagas del último mes

Given facturas de compra `docstatus = 1`, `status = Paid`, con `posting_date` dentro del último mes
When se arma el panel
Then se listan esas facturas
And cada fila incluye **proveedor**, **importe**, **fecha**, **plan de cuenta** y **centro de costo** (de los ítems).

---

## Scenario: lista de cobros recibidos

Given `Payment Entry` con `payment_type = Receive`, `docstatus = 1` en el último mes
When se arma el panel
Then se listan esos cobros
And cada fila incluye **parte**, **importe**, **fecha**, **plan de cuenta** y **centro de costo** tomados de la **factura de venta referenciada** en el cobro.

---

## Scenario: sidebar del club presente en Tesorería

Given el workspace `Tesorería`
When se abre en el Desk
Then se renderiza la navegación del club (`is_club_workspace` reconoce `Tesorería`).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Gate de acceso | `finance/permissions.py` (`ensure_finance_panel_access`) |
| Servicio de datos | `finance/services/tesoreria_panel.py` |
| API whitelisted | `finance/api/tesoreria_panel.py` |
| Permisos Purchase Invoice | `finance/setup/purchase_invoice_permissions.py` + patch |
| Panel (UI) | `public/js/tesoreria_workspace_panel.js`, `public/scss/tesoreria_workspace_panel.scss` |
| Navegación | `public/js/club_desk_navigation.js` |
| Workspace | `finance/workspace/tesoreria/tesoreria.json` |
| Tests | `tests/test_tesoreria_panel.py`, `tests/test_secretaria_finance_permissions.py` |
