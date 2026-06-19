# Spec: Segundo vencimiento y recargo fin de mes

Si la factura del mes no está pagada al **segundo vencimiento**, se aplica un **recargo configurable** sobre el saldo impago.

**Relacionado:** `cobranza_periodica_mensual.md`, `cobranza_config_club_settings.md`, `moroso_automatico.md`

---

## Definiciones

- **1er vencimiento:** `due_date` de la factura mensual (default día 10).
- **2do vencimiento:** último día del mes calendario de esa factura (o día fijo en `Club Settings`).
- **Recargo:** `recargo_segundo_vencimiento_pct` % sobre saldo impago de la factura mensual al cierre del 1er vencimiento.

---

## Scenario: aplicar recargo el día del segundo vencimiento

Given una `Sales Invoice` mensual con `periodo_cobro = 05/2026`
And `due_date` = 10/05/2026 (1er vencimiento)
And saldo pendiente > 0 al 10/05/2026
And hoy es el **2do vencimiento** de mayo 2026
When corre el job `aplicar_recargos_segundo_vencimiento`
Then se crea **una** de las siguientes (elegir en implementación; spec recomienda **opción A**):

**Opción A (recomendada):** `Debit Note` o segunda `Sales Invoice` de recargo con una línea `item_recargo_mora` por el monto calculado.

**Opción B:** línea adicional en la misma factura si aún editable (no recomendado si ya submitted).

And el monto de recargo = `saldo_pendiente_1er_vencimiento * recargo_pct / 100`
And queda registro idempotente (no duplicar recargo del mismo período).

---

## Scenario: factura pagada antes del 2do vencimiento

Given saldo de la factura mensual = 0 antes del 2do vencimiento
When corre el job de recargo
Then no se aplica recargo para ese período.

---

## Scenario: pago parcial antes del 2do vencimiento

Given saldo pendiente = 5000 al día 10
And recargo = 10%
When se aplica recargo el último día del mes
Then recargo = 500 (10% de 5000), no sobre el total original de la factura.

---

## Scenario: item de recargo no configurado

Given `item_recargo_mora` vacío en `Club Settings`
When el job intenta aplicar recargo
Then registra error en log y omite ese socio (no falla todo el batch).

---

## Scenario: sincronización saldo_deuda

Given se aplicó recargo
When finaliza el job
Then `Socio.saldo_deuda` refleja factura original + recargo pendiente.

---

## Scheduler

Mismo patrón diario que cobranza periódica: ejecutar solo si hoy == 2do vencimiento del mes.

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | `members/services/cobranza_recargo.py` |
| Job | `members/jobs/cobranza_periodica.py` (mismo módulo) |
| Tests | `members/tests/test_cobranza_recargo_segundo_vencimiento.py` |
