# Spec: Excepción Horario Día — ajuste puntual sin tocar grilla semanal

Cuando un partido (u otra reserva) solapa un entrenamiento de la grilla,
Coordinación debe poder **mover o acortar ese entrenamiento solo ese día**
sin editar `Horario Entrenamiento` del Espacio.

**Relacionado:** `spaces_fixtures_partidos.md`, `spaces_catalogo_ocupacion.md`.

---

## Scenario: reubicar cancha y/o horario del día

Given un `Horario Entrenamiento` en Cancha 3 los martes 19:00–21:00
And el 2026-10-20 (martes) hay un partido que solapa
When Coordinación crea `Excepcion Horario Dia` Activa:
  fecha=2026-10-20, espacio_origen=Cancha 3, horario_row=<name>,
  espacio_destino=Cancha 1, hora_desde=18:00, hora_hasta=19:00
Then `get_occupancy(Cancha 3, 2026-10-20)` **no** incluye el slot 19:00–21:00 de grilla
And `get_occupancy(Cancha 1, 2026-10-20)` incluye el bloque excepcional 18:00–19:00
And la child table del Espacio Cancha 3 sigue con el martes 19:00–21:00.

## Scenario: solo ajustar duración (misma cancha)

Given el mismo horario de grilla
When la excepción usa el mismo espacio_destino y hora_desde=19:00, hora_hasta=20:00
Then ese día la ocupación muestra 19:00–20:00 (no 19:00–21:00).

## Scenario: anular restaura grilla

Given una excepción Activa
When pasa a estado Anulada
Then ese día vuelve a mostrarse el slot original de la grilla.

---

## Scenario: suspender entrenamiento solo ese día

Given un `Horario Entrenamiento` en Cancha 3 los martes 19:00–21:00
When Coordinación crea `Excepcion Horario Dia` Activa con `accion = Suspender`
  para fecha 2026-10-20 y esa fila de horario
Then `get_occupancy(Cancha 3, 2026-10-20)` **no** incluye el slot de grilla
And **no** se crea bloque destino ese día
And la grilla semanal del Espacio no cambia.

---

## Scenario: API Desk desde planilla

Given rol Coordinacion
When llama `reubicar_horario_dia` con fecha, espacio_origen, horario_row, destino y horas
Then se crea la excepción Activa e idempotente (re-guardar actualiza la misma clave fecha+horario_row).
