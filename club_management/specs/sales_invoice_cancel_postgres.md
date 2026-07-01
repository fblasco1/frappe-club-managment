# Cancelación de Sales Invoice en PostgreSQL (bug B1)

## Contexto

En sitios **PostgreSQL**, cancelar una `Sales Invoice` enviada falla durante
`delink_original_entry` (ERPNext) porque el query builder asigna `delinked=true`
(boolean) a una columna `Check` almacenada como **smallint**.

## Escenarios

### Scenario: Secretaría cancela factura sin pagos

- **Given** un sitio con ERPNext y PostgreSQL
- **And** un socio activo con `Customer` vinculado
- **And** una `Sales Invoice` enviada (`docstatus=1`) sin `Payment Entry`
- **When** Secretaría cancela la factura
- **Then** la factura queda con `docstatus=2` (Cancelled)
- **And** las entradas de Payment Ledger originales quedan `delinked=1`

### Scenario: Parche idempotente al cargar la app

- **Given** un worker Frappe en PostgreSQL
- **When** se ejecuta `club_management.integrations.payment_ledger_postgres.apply_patch()`
- **Then** `delink_original_entry` usa valores smallint (`1`) y no booleanos
- **And** `get_negative_outstanding_invoices` usa parámetros SQL para `voucher_type`
- **And** ejecutar `apply_patch()` nuevamente no duplica el reemplazo

### Scenario: Registrar cobro manual sin error SQL

- **Given** un socio activo con factura mensual pendiente
- **When** Secretaría registra el cobro manual contra esa factura
- **Then** se crea un `Payment Entry` enviado
- **And** la factura queda con `outstanding_amount = 0`
- **And** `QueryPaymentLedger` agrupa cobros y facturas por comprobante (no por `posting_date`)

## Implementación

- Parche runtime en `integrations/payment_ledger_postgres.py` (sin modificar `erpnext`).
- Tests en `club_management/tests/test_sales_invoice_cancel_postgres.py` y `test_registrar_cobro_postgres.py`.
