# Spec: Deuda pendiente visible en formulario Socio

Secretaría debe ver en cada `Socio` el **saldo impago** y el **detalle de conceptos** que lo componen.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `cargo_extra_socio.md`, `cobranza_periodica_mensual.md`

---

## Scenario: panel de deuda muestra el mes / período

Given un `Socio` con una `Sales Invoice` pendiente con `periodo_cobro = 03/2026`
When Secretaría abre el formulario `Socio` y ve **Detalle de deuda**
Then cada fila de factura muestra el **período** (p. ej. `03/2026`)
And el diálogo **Registrar cobro** también indica el período junto al concepto.

---

## Scenario: detalle de deuda ordenado por período cronológico

Given un `Socio` con facturas pendientes de períodos `12/2025` y `01/2026` (y opcionalmente `03/2026`)
When Secretaría consulta `list_facturas_pendientes` / el panel **Detalle de deuda**
Then las filas aparecen ordenadas por período calendario ascendente (`12/2025` antes de `01/2026`)
And **no** por orden lexicográfico de `MM/YYYY` ni solo por `posting_date`.

---

## Scenario: diálogo Registrar cobro muestra total con mora al abrir

Given un `Socio` con cuota atrasada sujeta a mora al cobro
When Secretaría abre **Registrar cobro**
Then ve un resumen con el **total a cobrar** (incluyendo recargos %)
And por cada factura seleccionada la **composición** (valor actual × factores = exigido)
And el monto del medio de pago se actualiza a ese total (si no hay segundo medio)
And al cambiar la **fecha de cobro** el resumen se recalcula.

---

## Scenario: al marcar/desmarcar facturas se recalcula mora y montos

Given el diálogo **Registrar cobro** abierto con varias facturas
When Secretaría marca o desmarca facturas (o usa seleccionar/deseleccionar todas)
Then el resumen de mora y el **Monto medio 1** se actualizan al total exigido de la selección
And las etiquetas de cada factura muestran el monto **con mora** (no solo el outstanding histórico)
And al confirmar con un solo medio, el cobro usa ese total (sin error de “no coinciden”).

---

## Scenario: panel de deuda en Desk

Given un `Socio` con facturas ERPNext impagas y/o cargos extra pendientes
When Secretaría abre el formulario `Socio`
Then ve una sección **Deuda pendiente** con el total (`saldo_deuda`)
And una tabla con conceptos: facturas submitteadas con saldo (líneas **aún impagas**) y cargos `Cargo Socio` pendientes sin facturar.
And si la SI está paga en forma parcial, las líneas se netean con el **concepto del comprobante** (`reference_no` INF-…): un cobro de cuota social no deja la cuota en deuda ni se muestra como arancel; un cobro de tira (PRE-MINI / MINI / Cadetes…) cubre el arancel.
And la sincronización de `saldo_deuda` **no** actualiza `Socio.modified` (evita conflicto al guardar otros campos).

---

## Scenario: detalle de deuda — mora huérfana post-migración

Given un `Socio` con SI base **Paid** y SI ajuste `*-MORA` impaga creada por error
  (p. ej. posting en septiembre sin PE)
When Secretaría ve **Detalle de deuda**
Then esa mora aparece como saldo (correcto contablemente mientras exista)
And el script `cancelar_mora_huerfana_socio` puede cancelarla si el origen está Paid
  y no tiene Payment Entry asociado.

---

## Scenario: cargar panel de deuda no invalida el formulario

Given Secretaría abrió el formulario `Socio` y editó campos (p. ej. nombre)
When el panel **Deuda pendiente** sincroniza el saldo en segundo plano
And Secretaría guarda el socio
Then el guardado **no** falla por «modified after you have opened it».

---

## Scenario: generar cargo manual incluye cargos extra recurrentes

Given `Club Settings.incluir_cargos_extra_en_deuda_mensual = 1`
And un `Cargo Socio` recurrente vigente en estado `Pendiente`
When Secretaría ejecuta **Generar cargo** en el formulario `Socio`
Then la `Sales Invoice` incluye cuota/aranceles y el cargo extra recurrente
And `Socio.saldo_deuda` refleja el saldo ERPNext.

---

## Scenario: facturar cargo único actualiza deuda

Given un `Cargo Socio` `Unico` en `Pendiente`
When Secretaría ejecuta **Facturar cargo**
Then se crea y confirma la `Sales Invoice` sin error en PostgreSQL
And el cargo aparece en el detalle de deuda del socio.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio detalle | `members/services/cobranza_manual.py` |
| API Desk | `members/api/cobranza_desk.py` |
| UI Socio | `members/doctype/socio/socio.js` |
| Parche PG | `integrations/payment_ledger_postgres.py` |
| Tests | `members/tests/test_deuda_socio_desk.py` |
