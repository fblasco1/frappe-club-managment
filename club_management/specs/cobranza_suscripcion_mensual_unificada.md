# Spec: Cobranza mensual unificada vía suscripciones

Cuotas sociales y aranceles de actividades (inscripciones activas) se registran como **planes
en suscripciones ERPNext** del socio. La **emisión de deuda** respeta el calendario del club
configurado en `Club Settings`.

**Relacionado:** `cobranza_config_club_settings.md`, `cuotas_sociales_suscripcion.md`,
`cobranza_periodica_mensual.md`, `cobranza_recargo_segundo_vencimiento.md`,
`inscripcion_gestion_desk.md`

---

## Calendario (defaults ICDPE)

| Evento | Día | Campo `Club Settings` |
|--------|-----|------------------------|
| Emisión de deuda | **1** de cada mes | `dia_generacion_deuda` |
| 1.er vencimiento | **10** de cada mes | `dia_primer_vencimiento` |
| 2.º vencimiento | **Último día** del mes | `dia_segundo_vencimiento` |
| Recargo por mora | Al 2.º vencimiento, sobre saldo impago | `recargo_segundo_vencimiento_pct` + `item_recargo_mora` |

---

## Modelo de suscripción

### Una suscripción activa por `Customer` (socio facturable)

- **Cuota social:** un `Subscription Plan` según categoría del socio (`Club Settings.cuotas_categoria`).
- **Aranceles:** un `Subscription Plan` por cada `Inscripcion Actividad` **activa** (ítem del grupo/equipo/actividad).
- Alta / baja de planes al validar socio, inscribir actividad o dar de baja inscripción/socio.
- **`submit_invoice = 0`** en la suscripción: ERPNext **no** factura por su propio ciclo aniversario
  (evita duplicar y desalinear fechas). La factura mensual la emite el job del club (ver abajo).

### Socios elegibles a facturación mensual

`estado` ∈ {`Activo`, `Moroso`}. Excluir `Baja`, `Vitalicio` (cuota 0), pendientes y `Suspendido`.

---

## Scenario: alta de cuota social al validar socio

Given un `Socio` pasa a flujo post-validación (Solicitud o alta Secretaría)
And tiene categoría con cuota > 0 en `Club Settings`
When corre `enroll_socio_cuota_social`
Then se agrega el plan de cuota social a la suscripción activa del `Customer`
And no se genera factura inmediata (`submit_invoice = 0`).

---

## Scenario: alta de arancel al inscribir actividad

Given un `Socio` `Activo` con `Customer` ERPNext
And Secretaría confirma una `Inscripcion Actividad` activa con ítem de arancel resuelto
When se confirma la inscripción
Then se agrega el `Subscription Plan` del arancel a la suscripción del socio
And no se duplica el plan si ya estaba vigente para el mismo ítem.

---

## Scenario: baja de arancel al dar de baja inscripción

Given una `Inscripcion Actividad` activa con plan de arancel en la suscripción
When Secretaría da de baja la inscripción
Then se quita el plan de arancel de la suscripción (o se cancela la suscripción parcial según implementación)
And no se factura el mes siguiente ese arancel.

---

## Scenario: emisión de deuda el día 1

Given hoy es `dia_generacion_deuda` (default 1)
And socios con suscripción activa y planes vigentes
When corre el job `run_generar_deuda_si_corresponde`
Then se crea **una** `Sales Invoice` submitted por socio y período `MM/YYYY`
And `posting_date` ≥ hoy si la generación es tardía
And `due_date` = día `dia_primer_vencimiento` del mes (default 10), ajustado si cae antes de `posting_date`
And líneas = cuota social + aranceles de planes vigentes + cargos extra recurrentes (si flags en Club Settings)
And `Socio.saldo_deuda` se sincroniza
And no se duplica factura del mismo período (idempotencia).

---

## Scenario: segundo vencimiento y recargo

Given factura mensual con saldo > 0 al cierre del 1.er vencimiento
And hoy es el 2.º vencimiento del mes (`Ultimo dia del mes` por default)
When corre `run_recargos_si_corresponde`
Then se aplica recargo según `cobranza_recargo_segundo_vencimiento.md`
And no se duplica recargo del mismo período.

---

## Scenario: una sola fuente de facturación

Given un socio con `Subscription` activa
When Secretaría intenta **Generar cargo** desde Desk para un socio
And ya existe factura del período `MM/YYYY` o los ítems de cuota/arancel ya fueron facturados
Then la operación falla con error claro (no duplica conceptos en el mes)

---

## Estado de implementación (2026-07)

| Componente | Estado |
|------------|--------|
| Calendario en `Club Settings` | Hecho |
| Job día 1 + vencimiento 10 + recargo fin de mes | Hecho (`cobranza_periodica`) |
| Suscripción cuota social al validar | Hecho |
| Suscripción arancel al inscribir | **Pendiente** |
| `submit_invoice = 0` (evitar doble facturación) | **Hecho** |
| Unificar planes en una suscripción por Customer | **Hecho** |
| Idempotencia cuota/arancel por mes (Secretaría) | **Hecho** |
| Script padrón + deuda | `members/setup/sync_suscripciones_padron.py` |

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Suscripciones socio | `members/services/suscripciones_socio.py` |
| Bootstrap planes | `setup/suscripciones_cobro_mensual.py` |
| Emisión mensual | `members/services/cobranza_periodica.py` |
| Jobs scheduler | `members/jobs/cobranza_periodica.py`, `hooks.py` |
| Tests suscripción cuota | `members/tests/test_suscripciones_socio_integracion.py` |
| Tests cobranza mensual | `members/tests/test_cobranza_periodica_mensual.py` |
