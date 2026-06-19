# Spec: Generación mensual de deuda (día 1)

Job programado que emite deuda a todos los socios elegibles el **primer día** (configurable) de cada mes, con **vencimiento día 10**.

**Relacionado:** `cobranza_config_club_settings.md`, `cuotas_sync_erpnext.md`, `cargo_extra_socio.md`  
**Prerequisito:** ERPNext (`Sales Invoice`) instalado.

---

## Socios elegibles

Incluir socios con `estado` en:
- `Activo`
- `Moroso` (nueva deuda del mes igualmente; moroso se reevalúa aparte)

Excluir:
- `Baja`, `Vitalicio` (cuota 0), `Pendiente de Validación`, `Pendiente de Pago`, `Pendiente de Inscripción`, `Suspendido` (configurable; default excluir Suspendido).

---

## Scenario: job día 1 genera factura por socio activo

Given hoy es `dia_generacion_deuda` del mes (default día 1)
And `Club Settings` configurado
And un `Socio` `Activo` con `Customer` ERPNext
When corre el job `generar_deuda_mensual_socios`
Then se crea una `Sales Invoice` submitted por socio
And `due_date` = día `dia_primer_vencimiento` del mes corriente (o mes siguiente si generación tardía; documentar regla: **mismo mes calendario**)
And la factura referencia `Socio` (campo custom)
And líneas incluyen:
  - Cuota social (`resolve_cuota_social`) si monto > 0
  - Cada arancel de `Inscripcion Actividad` activa si `incluir_aranceles_en_deuda_mensual`
  - Cargos extra recurrentes vigentes si `incluir_cargos_extra_en_deuda_mensual`
And `Socio.saldo_deuda` se sincroniza tras emitir.

---

## Scenario: fechas válidas si la generación es tardía en el mes

Given `reference_date` del período es anterior a hoy (p. ej. día 1 del mes y hoy es día 15)
When se ejecuta `generar_deuda_mensual_socio`
Then `posting_date` no es anterior a hoy
And `due_date` >= `posting_date`
And la factura se submittea sin error ERPNext.

---

## Scenario: idempotencia mismo mes

Given el job ya generó factura de «cuota mensual {MM/YYYY}» para un socio
When el job vuelve a correr el mismo mes
Then no duplica factura (detectar por `remarks` / campo custom `periodo_cobro` / naming).

---

## Scenario: socio sin Customer

Given socio elegible sin `Customer`
When corre el job
Then crea `Customer` vía `ensure_customer_for_socio` y continúa
Or registra error en log y omite socio (elegir: **crear Customer automático**).

---

## Scenario: arancel desde grupo o actividad

Given inscripción activa con `grupo_actividad` que tiene `item`
When se arma la factura
Then la línea usa `resolve_item_arancel_inscripcion` y monto de `Item.standard_rate` o `Item Price`.

---

## Scenario: desactivar suscripción ERPNext duplicada

Given el socio tiene `Subscription` activa que también genera facturas de cuota social
When se habilita cobranza periódica custom
Then **una sola fuente** de facturación mensual (config: desactivar `submit_invoice` en Subscription o excluir cuota social del job si Subscription activa).

**Decisión por implementar:** documentar en código; spec recomienda **job club como fuente única** y cancelar suscripciones ERPNext de cuota al migrar a fase 2.

---

## Registro de ejecución

Crear `Cobranza Mensual Log` (DocType opcional) o entrada en Error Log / custom log con: período, socios procesados, facturas creadas, omitidos, errores.

---

## Scheduler

```python
# hooks.py
scheduler_events = {
    "daily": [
        "club_management.members.jobs.cobranza_periodica.run_generar_deuda_si_corresponde",
    ],
}
```

El job diario verifica si hoy == `dia_generacion_deuda` (y no corrió ya este mes).

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | `members/services/cobranza_periodica.py` |
| Job | `members/jobs/cobranza_periodica.py` |
| Campo custom SI | `periodo_cobro` en Sales Invoice (patch) |
| Tests | `members/tests/test_cobranza_periodica_mensual.py` |
