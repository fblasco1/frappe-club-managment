# Spec: Flujo de egresos Borrador (Secretaría) → Aprobación (Tesorería)

Se elimina el uso de `Purchase Order` en el club. Todo egreso (servicios, presupuestos,
insumos, sueldos) se carga como **`Purchase Invoice`** usando el `docstatus` nativo:

- **Borrador** (`docstatus = 0`): registrado operativamente, **sin** deuda contable firme.
- **Presentado** (`docstatus = 1`): deuda firme, entra en libros y en la proyección de flujo.

**Relacionado:** `rol_tesoreria_permisos.md`, `tesoreria_panel_operaciones.md`, `carga_rapida_ingreso_egreso.md`

## Roles

- **Secretaría**: carga cualquier egreso en **Borrador**. Puede leer/crear/editar
  `Purchase Invoice` pero **no** puede Presentar (Submit) ni Cancelar. **No** tiene acceso a `Purchase Order`.
- **Tesorería**: permisos **totales** sobre `Purchase Invoice` (leer/crear/editar/**Presentar**/**Cancelar**/eliminar).
  Audita los borradores y aprueba o rechaza.

---

## Scenario: Secretaría carga un gasto en borrador

Given un usuario con rol `Secretaria`
When crea una `Purchase Invoice` con proveedor, ítem con centro de costo y `due_date`
Then puede guardarla en **Borrador** (`docstatus = 0`)
And **no** puede Presentarla (no tiene permiso `submit`).

---

## Scenario: Secretaría sin acceso a Órdenes de Compra

Given un usuario con rol `Secretaria` (o `Tesoreria`)
When intenta acceder a `Purchase Order`
Then no tiene permiso (los `Custom DocPerm` del club para `Purchase Order` fueron removidos).

---

## Scenario: Tesorería aprueba un borrador

Given una `Purchase Invoice` en Borrador
And un usuario con rol `Tesoreria`
When Presenta (Submit) la factura
Then queda en `docstatus = 1` (deuda firme)
And puede Cancelarla si corresponde.

---

## Scenario: validación estricta de due_date y centro de costo

Given una `Purchase Invoice`
When se guarda sin `due_date` **o** con algún ítem sin `cost_center`
Then el sistema lanza `ValidationError` (hook `validate`).

---

## Scenario: carga rápida crea borrador

Given `registrar_egreso(...)`
When se ejecuta
Then crea la `Purchase Invoice` en **Borrador** (`docstatus = 0`), sin Presentar ni pagar.

---

## Scenario: flujo de fondos incluye borradores como gasto proyectado

Given `Purchase Invoice` en Borrador con `due_date` dentro de la ventana
When Tesorería consulta la proyección de flujo de fondos
Then el monto figura como **Gastos proyectados (pendientes de aprobación)**, separado de los
**Pagos comprometidos** (facturas presentadas con saldo).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Permisos Purchase Invoice | `finance/setup/purchase_invoice_permissions.py` + patch |
| Remoción Purchase Order | `finance/setup/purchase_order_permissions.py` (`remove_purchase_order_club_permissions`) + patch |
| Validación egreso | `finance/services/purchase_invoice_validation.py` (`validate_egreso`) + `hooks.py` |
| Carga rápida (draft) | `finance/services/carga_rapida.py` (`registrar_egreso`) |
| Panel borradores | `finance/services/tesoreria_panel.py` (`facturas_compra_borrador`), `public/js/tesoreria_workspace_panel.js` |
| Botón Secretaría | `public/js/secretaria_workspace_panel.js` |
| Flujo de fondos | `finance/services/flujo_fondos.py`, `finance/report/proyeccion_flujo_de_fondos/` |
| Tests | `finance/tests/test_purchase_invoice_flujo.py`, `tests/test_tesoreria_panel.py`, `tests/test_flujo_fondos.py`, `tests/test_secretaria_finance_permissions.py` |
