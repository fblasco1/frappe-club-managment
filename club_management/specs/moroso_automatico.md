# Spec: Moroso automático post segundo vencimiento

El sistema debe pasar a **Moroso** al socio que no registró pago de **cuota social y aranceles** del período una vez vencido el **segundo vencimiento**.

**Relacionado:** `cobranza_recargo_segundo_vencimiento.md`, `mvp_operacion_secretaria_sin_pagos.md`

---

## Regla de negocio

Given un `Socio` en estado `Activo`
And existe deuda del período corriente (factura mensual + recargo si aplica) con saldo > 0
And la fecha actual es **estrictamente posterior** al 2do vencimiento de ese período
When corre el job `evaluar_morosos_automatico`
Then `estado` pasa a `Moroso`
And se registra auditoría (`motivo_ultimo_cambio_estado` = «Moroso automático — impago período MM/YYYY»).

---

## Scenario: no moroso si pagó todo

Given saldo total ERPNext del socio = 0 para el período
When corre el job
Then el socio permanece `Activo`.

---

## Scenario: socio ya Moroso

Given `estado = Moroso`
When corre el job
Then no se duplica transición ni se resetea auditoría.

---

## Scenario: socio Suspendido o Baja

Given `estado` en `Suspendido`, `Baja`, `Vitalicio`
When corre el job
Then no se modifica el estado.

---

## Scenario: reactivación al pagar (existente)

Given socio `Moroso` con saldo > 0
When Secretaría registra cobro y saldo queda 0
Then `registrar_cobro_manual` reactiva a `Activo` (comportamiento actual — mantener).

---

## Scenario: solo cuota y aranceles cuentan para moroso automático

Given cargo extra «Viaje Santa Fe» impago pero cuota + aranceles del mes pagados
When corre el job
Then **no** pasa a Moroso por el viaje solo (cargos extra no disparan moroso automático en v1).

**Iteración 2:** flag en `Club Settings` para incluir todos los saldos.

---

## Orden de jobs el último día del mes

1. `aplicar_recargos_segundo_vencimiento` (si corresponde)
2. `evaluar_morosos_automatico` (mismo día o día siguiente; spec: **mismo día, después del recargo**)

---

## Scheduler

```python
"daily": [
    "club_management.members.jobs.moroso_automatico.run_evaluar_morosos_si_corresponde",
]
```

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | `members/services/moroso_automatico.py` |
| Job | `members/jobs/moroso_automatico.py` |
| Tests | `members/tests/test_moroso_automatico.py` |
