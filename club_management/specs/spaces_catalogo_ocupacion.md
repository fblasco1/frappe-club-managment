# Spec: Espacios — catálogo, grilla y ocupación interna

Infraestructura física del club (canchas, gimnasios, salones) separada del
catálogo de actividades (`Actividad` → `Grupo Actividad` → `Equipo Actividad`).

**Módulo:** Spaces  
**Roles:** `Coordinacion` (escritura Desk), `Secretaria` (escritura), `Tesoreria`
(solo lectura), `System Manager` (full).

**Alcance de este tramo:** catálogo de `Espacio`, grilla semanal
`Horario Entrenamiento`, ocupación puntual `Reserva Espacio` cargada por Desk.
Sin portal socio, sin alquiler cobrado a externos.

**Relacionado:** `gestion_actividades_dashboard.md`, `activities_jerarquia.md`,
`spaces_fases_futuras.md`.

---

## Modelo

```
Espacio (Cancha 1, Gimnasio, Salón…)
├── alquilable (metadato; inerte en este tramo)
├── horarios[] → Horario Entrenamiento (grilla semanal recurrente)
└── Reserva Espacio (ocupación puntual: uso interno / evento / bloqueo)
```

- **Actividad** = disciplina / plan (quién se inscribe).
- **Espacio** = lugar físico.
- Un horario puede vincularse a actividad/grupo/equipo o usar `titulo` libre.
- Solo reservas con `estado = Confirmada` ocupan el calendario.

---

## Scenario: crear espacio alquilable

Given un usuario con rol `Coordinacion`
When crea un `Espacio` con `titulo = Cancha 1`, `tipo = Cancha`, `alquilable = 1`
Then el documento se guarda habilitado
And `alquilable = 1` no restringe entrenamientos ni reservas internas en este tramo.

---

## Scenario: espacio no alquilable

Given un usuario `Coordinacion`
When crea `Espacio` «Gimnasio musculación» con `alquilable = 0`
Then el espacio se guarda
And puede tener grilla de horarios de entrenamiento igual que uno alquilable.

---

## Scenario: grilla semanal sin solape

Given `Espacio` «Cancha 1»
When se cargan dos `Horario Entrenamiento` el mismo día `Lunes` 18:00–19:00 y 19:00–20:00
Then el documento se guarda sin error.

---

## Scenario: varios equipos en el mismo horario de cancha

Given `Espacio` «Cancha 1»
When se cargan dos `Horario Entrenamiento` el mismo día con franjas solapadas (18:00–19:30 y 19:00–20:00) para equipos distintos
Then el documento se guarda sin error
And cada fila mantiene su Actividad / Grupo / Equipo.

---

## Scenario: tipo de sesión preparación física o entrenamiento deportivo

Given un `Horario Entrenamiento` con `tipo_sesion = Preparación física` y vínculos a actividad/grupo/equipo
When se valida el `Espacio`
Then se guarda correctamente
And el `titulo` incluye el tipo de sesión (p. ej. «Preparación física — Basquet / Masculino / U11»).

Given un horario con `tipo_sesion = Entrenamiento deportivo`
When se valida
Then el título refleja el entrenamiento deportivo y los vínculos.

---

## Scenario: horario hasta debe ser mayor que desde

Given una fila de `Horario Entrenamiento` con `hora_desde = 19:00` y `hora_hasta = 18:00`
When se valida el `Espacio`
Then se lanza `ValidationError`.

---

## Scenario: vínculo grupo/equipo coherente con actividad

Given `Actividad` Basquet, `Grupo Actividad` Masculino y `Equipo Actividad` U11
When un horario en Cancha 1 apunta a ese equipo (y actividad/grupo correctos)
Then se guarda correctamente.

Given un `Equipo Actividad` de otra actividad
When se intenta vincularlo en el horario con una actividad distinta
Then se lanza `ValidationError`.

---

## Scenario: grilla muestra Actividad, Grupo/Tira y Equipo; título concatenado

Given un `Horario Entrenamiento` con `tipo_sesion = Entrenamiento deportivo`, actividad «Basquet», grupo «Masculino» y equipo «U11»
When se valida el `Espacio`
Then `titulo` queda como concatenación incluyendo el tipo (p. ej. «Entrenamiento deportivo — Basquet / Masculino / U11»)
And en la grilla Desk se ven columnas Tipo de sesión, Actividad, Grupo/Tira y Equipo
And `titulo` es de solo lectura (no se edita a mano).

---

## Scenario: reserva confirmada bloquea el slot

Given `Espacio` «Salón» sin solape en grilla ese día
When `Coordinacion` crea `Reserva Espacio` Confirmada el 2026-09-01 de 15:00 a 18:00 tipo `Evento club`
Then la reserva se guarda
And otra reserva Confirmada solapada en el mismo espacio/fecha se rechaza con `ValidationError`.

---

## Scenario: borrador y cancelada no ocupan

Given una `Reserva Espacio` en `Borrador` o `Cancelada` en un slot
When se crea otra reserva `Confirmada` en el mismo slot
Then se acepta (no hay conflicto con borradores/canceladas).

---

## Scenario: reserva confirma conflicto con grilla semanal

Given `Espacio` con horario recurrente Lunes 18:00–20:00
And la fecha pedida es un lunes
When se intenta confirmar una reserva 18:30–19:30 ese día
Then se lanza `ValidationError` por solape con la grilla.

---

## Scenario: tipos de reserva de este tramo

Given `Reserva Espacio`
Then `tipo` admite `Uso interno`, `Evento club`, `Bloqueo` y `Alquiler externo`
And el detalle de alquiler Temporal/Recurrente está en `spaces_alquiler_externo.md`.

---

## Scenario: permisos Coordinacion escribe

Given usuario solo con rol `Coordinacion`
When crea o edita `Espacio` y `Reserva Espacio`
Then tiene permiso
And `has_app_permission` de la app SICLUB es verdadero.

---

## Scenario: Tesoreria solo lectura

Given usuario solo con rol `Tesoreria`
When intenta crear `Espacio` o `Reserva Espacio`
Then no tiene permiso de escritura
And puede leer ambos DocTypes.

---

## Scenario: Socio sin Desk en espacios

Given usuario con rol `Socio` (portal)
When consulta acceso a la app Desk / DocTypes de Spaces
Then no tiene create/write sobre `Espacio` ni `Reserva Espacio`
And `has_app_permission` es falso.

---

## Scenario: dashboard actividades enlaza infraestructura

Given el módulo Spaces modelado
When Secretaria consulta el dashboard de Gestión de Actividades
Then `infraestructura.disponible = true`
And el payload incluye ruta/enlace al workspace `Espacios`
And ya no muestra solo «Próximamente».

---

## Fuera de alcance (este tramo)

- Reserva desde portal del socio o equipo.
- Cobro online / Sales Invoice automático de alquileres (ver `spaces_alquiler_externo.md` y `spaces_fases_futuras.md`).
- Multi-sede.
