# Spec: Suspensión Reserva Día — cancelar ocupación puntual sin tocar la reserva base

Permite **suspender** una `Reserva Espacio` Confirmada **solo en una fecha**
(partido fixture, evento club recurrente, alquiler recurrente, reserva puntual)
sin cambiar estado global de la reserva ni la grilla semanal.

**Relacionado:** `spaces_excepcion_horario_dia.md`, `spaces_ocupacion_dashboard.md`

---

## Scenario: suspender reserva puntual del día

Given `Reserva Espacio` Confirmada tipo `Evento club` el 2026-09-05 14:00–16:00
When Coordinación crea `Suspension Reserva Dia` Activa para esa fecha y reserva
Then `get_occupancy(espacio, 2026-09-05)` **no** incluye esa reserva
And el documento `Reserva Espacio` sigue Confirmada.

---

## Scenario: anular suspensión restaura ocupación

Given una suspensión Activa
When pasa a estado Anulada
Then ese día la reserva vuelve a ocupar el calendario.

---

## Scenario: API Desk desde planilla

Given rol Coordinacion
When llama `suspender_reserva_dia` con fecha, reserva y motivo
Then se crea la suspensión Activa e idempotente (misma clave fecha+reserva).
