# Spec: Fecha de cobro en registrar cobro manual

Secretaría debe poder indicar **cuándo se realizó** el cobro al cargarlo en el sistema (carga tardía).

**Relacionado:** `secretaria_operacion_interna_mvp.md`, `recibo_pago_escpos.md`

---

## Scenario: registrar cobro con fecha pasada

Given una `Sales Invoice` pendiente del socio
When Secretaría registra cobro con `posting_date = 2026-07-03`
Then el `Payment Entry` submitted tiene `posting_date = 2026-07-03`
And `reference_date` del PE coincide con esa fecha.

---

## Scenario: fecha omitida usa hoy

Given Secretaría no indica fecha
When registra cobro manual
Then `posting_date` del `Payment Entry` es hoy.

---

## Scenario: fecha futura rechazada

Given Secretaría indica `posting_date` posterior a hoy
When intenta registrar cobro
Then error de validación.

---

## Scenario: formulario Socio — diálogo registrar cobro

Given Secretaría abre **Registrar cobro** en formulario `Socio`
Then el campo **Fecha de cobro** está **arriba de todo** en el diálogo (antes de facturas y medios)
And puede elegir **Fecha de cobro** (default hoy)
When confirma el medio de pago
Then el cobro usa esa fecha para mora y para el `Payment Entry`.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `members/services/cobranza_manual.py` |
| API | `members/api/cobranza_desk.py` |
| JS | `members/doctype/socio/socio.js` |
| Tests | `tests/test_registrar_cobro_postgres.py` |
