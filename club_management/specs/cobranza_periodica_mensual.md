# Spec: Generación mensual de deuda (día 1)

Job programado que emite deuda a todos los socios elegibles el **primer día** (configurable) de cada mes, con **vencimiento día 10**.

**Relacionado:** `cobranza_config_club_settings.md`, `cuotas_sync_erpnext.md`, `cargo_extra_socio.md`  
**Prerequisito:** ERPNext (`Sales Invoice`) instalado.

---

## Socios elegibles

Incluir socios con `estado` en:
- `Activo`
- `Moroso` (nueva deuda del mes igualmente; moroso se reevalúa aparte)
- `Vitalicio`: la cuota social resuelve a 0, así que solo se factura si tiene aranceles
  de actividades o cargos extra; sin líneas no se emite factura.

Excluir:
- `Baja`, `Pendiente de Validación`, `Pendiente de Pago`, `Pendiente de Inscripción`, `Suspendido` (configurable; default excluir Suspendido).

---

## Scenario: vitalicio inscripto en una actividad paga solo el arancel

Given un `Socio` con `estado = Vitalicio` (categoría Vitalicio) inscripto en una actividad con arancel
When corre el job `generar_deuda_mensual_socios`
Then se emite su factura del mes con **solo** la línea del arancel (sin cuota social)
And un vitalicio sin actividades ni cargos no recibe factura.

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

## Scenario: arancel desde grupo sin equipo (deportes no-básquet)

Given inscripción activa en fútbol/vóley/patín/otras con `grupo_actividad.item` seteado
And `equipo_actividad` vacío
When se genera la deuda mensual del socio
Then la línea de arancel usa el ítem del **grupo/tira** (no el genérico de actividad).

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

El job diario es liviano: solo decide si corresponde y **encola** la generación en la cola `long`.

**Incidente 01/10/2026 (causa raíz):** la frecuencia `daily` corre en la cola `default` con timeout de **300 s**;
la generación (~1000 socios) tarda 8–16 min en una sola transacción. RQ mataba el work-horse a los 360 s
(«Work-horse terminated unexpectedly»), se revertía todo y no quedaba Error Log. Jul/Ago/Sep/Oct se generaron a mano.

### Reglas

- `DEUDA_JOB_TIMEOUT` = 2 h; `job_id` = `deuda_mensual_<MM-YYYY>` (deduplicado: no encola dos veces el mismo período).
- La ejecución encolada hace **commit por socio** (un corte no pierde lo ya emitido) y rollback del socio que falla.
- Al terminar el recorrido se marca el período como generado (`frappe.db.set_global(MARCA_DEUDA_MENSUAL, "MM/YYYY")`)
  y se registra un **resumen** en Error Log (`Deuda mensual MM/YYYY — resumen`).
- **Reintento:** desde `dia_generacion_deuda` y antes de `dia_primer_vencimiento`, si el período no está marcado,
  el job diario vuelve a encolar (idempotente por `factura_periodo_existe`).

## Scenario: el job diario encola la generación en la cola long

Given hoy es `dia_generacion_deuda`
And el período del mes no está marcado como generado
When corre `run_generar_deuda_si_corresponde`
Then se encola `ejecutar_generacion_deuda_mensual` en la cola `long`
And con `timeout` = `DEUDA_JOB_TIMEOUT` y `job_id` = `deuda_mensual_<MM-YYYY>`
And el job diario no genera facturas por sí mismo.

## Scenario: reintento si la generación anterior no terminó

Given hoy es posterior a `dia_generacion_deuda` y anterior a `dia_primer_vencimiento`
And el período del mes no está marcado como generado
When corre `run_generar_deuda_si_corresponde`
Then se vuelve a encolar la generación del período.

## Scenario: no reencola un período ya generado ni fuera de ventana

Given el período del mes ya está marcado como generado
Or hoy es igual o posterior a `dia_primer_vencimiento`
When corre `run_generar_deuda_si_corresponde`
Then no se encola nada.

## Scenario: ejecución encolada con commit por socio, marca y resumen

When corre `ejecutar_generacion_deuda_mensual(reference_date)`
Then llama `generar_deuda_mensual_socios(..., commit_por_socio=True)`
And marca el período como generado
And crea un Error Log `Deuda mensual MM/YYYY — resumen` con facturas creadas, omitidos y errores.

## Scenario: un socio con error no revierte a los demás (commit por socio)

Given `commit_por_socio=True`
And la factura de un socio falla
When corre `generar_deuda_mensual_socios`
Then se hace rollback solo de ese socio, se registra el error y se continúa con el resto.

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | `members/services/cobranza_periodica.py` |
| Job | `members/jobs/cobranza_periodica.py` |
| Campo custom SI | `periodo_cobro` en Sales Invoice (patch) |
| Tests | `members/tests/test_cobranza_periodica_mensual.py` |
