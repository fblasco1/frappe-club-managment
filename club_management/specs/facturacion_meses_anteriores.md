# Spec: Facturación de meses anteriores

Cuando el club no arranca en cero, Secretaría debe poder emitir la deuda de
**períodos pasados** (cuota social, aranceles y cargos extra recurrentes vigentes
en ese período) sin esperar al job del día 1 ni depender de «hoy».

**Relacionado:** `flujo_cobranzas.md`, `cobranza_periodica_mensual.md`,
`mvp_operacion_secretaria_sin_pagos.md`, `complementar_aranceles_periodo.md`

**Prerequisito:** ERPNext; servicios existentes aceptan `reference_date`
(`generar_cargo_socio`, `generar_deuda_mensual_socio`).

---

## Alcance

- Desk: en formulario `Socio`, **Generar cargo** permite elegir **período**
  (`MM/YYYY` o mes/año), default = mes corriente.
- Ops/batch: emitir deuda de un rango de meses para un socio o para todos los
  elegibles (script/API), con idempotencia por `periodo_cobro` + ítem.

**No incluye:** recalcular precios históricos con Item Price de otra fecha
(salvo que se documente después). Primera versión usa el **precio vigente hoy**
del ítem / cuota categoría al momento de emitir (documentar en UI).

---

## Scenario: Generar cargo de un mes pasado (un socio)

Given un `Socio` `Activo` o `Moroso` con `Customer`
And no existen facturas del período `03/2026` para sus conceptos
When Secretaría ejecuta **Generar cargo** con período `03/2026`
Then se crean `Sales Invoice` submitted por concepto pendiente (cuota / arancel /
cargos extra recurrentes vigentes en esa fecha si aplica)
And todas tienen `periodo_cobro = 03/2026`
And `due_date` respeta `dia_primer_vencimiento` del mes del período (o regla
`resolve_fechas_factura_mensual` ya existente)
And no se duplican conceptos ya facturados en ese período
And `Socio.saldo_deuda` se sincroniza.

---

## Scenario: Generar cargo del mes corriente sin cambiar UX

Given Secretaría no elige período explícito
When ejecuta **Generar cargo**
Then el período es el mes de `today()` (comportamiento actual).

---

## Scenario: mes ya facturado completo

Given todos los conceptos del período `03/2026` ya tienen SI
When Secretaría genera cargo para `03/2026`
Then error de validación claro («no hay conceptos pendientes…»)
And no se crean facturas.

---

## Scenario: batch rango de meses (ops)

Given meses `01/2026` … `03/2026` y un socio elegible
When se ejecuta `generar_deuda_rango_meses(socio, desde=2026-01-01, hasta=2026-03-01)`
  (o batch multi-socio)
Then se emite deuda idempotente por cada mes del rango
And meses ya emitidos se omiten sin error fatal del batch
And el resumen indica creadas / omitidas / errores.

---

## Scenario: permisos

Given usuario sin rol `Secretaria` / `System Manager`
When invoca la API con `periodo` o `reference_date`
Then `PermissionError`.

---

## UI Desk

- Diálogo en **Generar cargo**: selector mes/año (o Date del día 1 del mes).
- Texto de ayuda: «Usa precios vigentes al emitir; para deuda histórica de
  socios que ya debían cuotas al implementar el sistema».

---

## Artefactos esperados

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/facturacion_meses_anteriores.md` |
| Servicio | `members/services/cobranza_manual.py` / `cobranza_periodica.py` |
| API | `members/api/cobranza_desk.py` (`generar_cargo` + `reference_date`/`periodo`) |
| JS | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_facturacion_meses_anteriores.py` |
| Ops (opcional) | `members/ops/emitir_deuda_rango.py` |
