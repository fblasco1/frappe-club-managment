# Spec: Alquiler externo de espacios (Temporal y Recurrente)

Extiende `Reserva Espacio` para alquiler a **externos** de canchas/espacios
`alquilable`. Cobro (Sales Invoice / Cobrand) queda fuera de este tramo;
sí se ocupa el calendario y se tipifica Temporal vs Recurrente (alineado a
Cost Centers / ítems `ICDPE-ALQ-*-TEMP` y `ICDPE-ALQ-*-REC`).

**Relacionado:** `spaces_catalogo_ocupacion.md`, `spaces_fases_futuras.md`

---

## Scenario: alquiler temporal en espacio alquilable

Given `Espacio` «Cancha 1» con `alquilable = 1`
When Coordinacion crea `Reserva Espacio` Confirmada tipo `Alquiler externo`,
`modalidad_alquiler = Temporal`, fecha 2026-09-10, 18:00–20:00 y arrendatario «Club Visitante»
Then se guarda
And ocupa ese slot en el calendario.

---

## Scenario: alquiler externo exige espacio alquilable

Given `Espacio` «Gimnasio» con `alquilable = 0`
When se intenta confirmar `Alquiler externo`
Then se lanza `ValidationError`.

---

## Scenario: alquiler recurrente ocupa todos los días del patrón

Given `Espacio` alquilable
When se confirma `Alquiler externo` `modalidad_alquiler = Recurrente`
con `fecha_desde = 2026-09-01`, `fecha_hasta = 2026-09-30`, días `Martes` y `Jueves`, 19:00–21:00
Then en un martes dentro del rango (p. ej. 2026-09-01) el slot está ocupado
And en un miércoles del rango no ocupa por este alquiler
And otra reserva Confirmada solapada un martes a esa hora se rechaza.

---

## Scenario: recurrente exige rango y al menos un día

Given tipo `Alquiler externo` y modalidad `Recurrente`
When falta `fecha_desde`, `fecha_hasta` o no hay días en la tabla
Then se lanza `ValidationError`.

---

## Scenario: tipos internos siguen válidos

Given tipos `Alquiler socio`, `Evento club`, `Bloqueo`
When se guarda una reserva de esos tipos
Then no exige `modalidad_alquiler` ni datos de arrendatario externo.

---

## Fuera de alcance (este tramo)

- Generar Sales Invoice automáticamente.
- Cobro online Cobrand / Supervielle.
- Portal de reserva para el externo.
