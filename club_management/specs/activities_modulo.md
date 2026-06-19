# Módulo Activities — catálogo e inscripción post-pago

## Alcance (Sprint actual)

- Catálogo **`Actividad`** administrable en Desk (Secretaría / System Manager), alineado al
  plan ICDPE: cada actividad enlaza al **Item** de arancel mensual (`ICDPE-ARANCEL-MENSUAL-…`).
- Lista oficial (12): Basquet Masculino, Basquet Femenino, Voley Femenino, Futbol,
  Patin Artistico, Gimnasia Artistica, Iniciacion Deportiva, Danza, Gimnasio Fitness,
  Funcional, Crossfit, Zumba (contable: Ritmos Latinos).
- **`Inscripcion Actividad`**: vínculo Socio ↔ Actividad (una fila por par).
- Tras confirmar el **pago stub**, el socio pasa a **`Pendiente de Inscripción`** y debe
  elegir una o más actividades (o continuar sin ninguna) en una página pública firmada
  con el mismo `pago_token`.
- Al confirmar la inscripción, el socio pasa a **`Activo`** y el campo resumen
  `Socio.actividad` refleja los nombres separados por coma.
- El formulario público de solicitud y el panel Secretaría consumen el mismo catálogo.

## Scenario: catálogo de actividades habilitadas

Given existen registros `Actividad` con `habilitada = 1`
When se llama a `list_actividades_portal()`
Then devuelve `{value, label}` ordenados por `orden` y `titulo`
And solo incluye actividades habilitadas.

## Scenario: pago stub deja al socio pendiente de inscripción

Given una `Solicitud Asociacion` en `Validada` con `socio_generado`
And un `pago_token` válido para esa solicitud
When se ejecuta `confirmar_pago_stub` con ese token
Then el `Socio` queda con `estado = "Pendiente de Inscripción"`
And la respuesta incluye `inscripcion_url` hacia `/inscripcion-actividades?token=…`
And **no** queda `Activo` todavía.

## Scenario: inscripción pública tras el pago

Given el mismo `pago_token` y el socio en `Pendiente de Inscripción`
When el visitante envía `actividades = ["Natación", "Fútbol"]` (nombres de `Actividad`)
Then se crean `Inscripcion Actividad` activas para cada actividad válida
And `Socio.actividad` = `"Natación, Fútbol"` (resumen)
And `Socio.estado` = `"Activo"`.
And un segundo intento con el mismo token falla (socio ya no está pendiente).

## Scenario: inscripción vacía permitida

Given socio en `Pendiente de Inscripción`
When confirma sin seleccionar actividades
Then no se crean inscripciones
And el socio pasa a `Activo` con `Socio.actividad` vacío.

## Scenario: token o estado inválido

Given un `pago_token` inválido o expirado (solicitud inexistente)
When se intenta confirmar inscripción
Then el sistema responde error (404 / mensaje genérico).

Given un socio que **no** está en `Pendiente de Inscripción`
When se intenta confirmar inscripción con token válido
Then el sistema rechaza la operación.

## Scenario: listado Secretaría muestra actividades inscritas

Given un socio moroso con inscripciones activas a `Natación` y `Gimnasio`
When se arma la fila del panel de morosos
Then `actividad` muestra `"Natación, Gimnasio"` (o fallback a solicitud si no hay inscripciones).

## Seguridad

- Endpoints públicos usan el mismo `pago_token` firmado (no enumerable).
- `confirmar_inscripcion_actividades`: `allow_guest=True` + rate limit.
- Desk: permisos por rol en DocTypes; socios no administran el catálogo.

## Fuera de alcance (sprints posteriores)

- Cuotas por actividad, Cost Center, ERPNext `Item` obligatorio.
- Portal autenticado del socio para cambiar inscripciones.
- SIRO / Supervielle real (Sprint 4).
