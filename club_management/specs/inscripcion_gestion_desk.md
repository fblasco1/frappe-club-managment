# Spec: Gestión de inscripciones desde formulario Socio

Secretaría debe poder **ver**, **dar de baja** y (opcionalmente) **agregar** inscripciones sin salir del contexto del socio.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `activities_jerarquia.md`  
**Ya implementado:** alta vía botón «Inscribir en actividades» (`inscribir_actividades_desk`).

---

## Scenario: listar inscripciones activas del socio

Given un `Socio` con una o más `Inscripcion Actividad` en estado `Activa`
When Secretaría abre el formulario `Socio` o llama `list_inscripciones_socio_desk`
Then recibe filas con: `name`, actividad, grupo, equipo, `fecha_inscripcion`, ítem arancel resuelto, monto
And solo incluye inscripciones `Activa` por defecto (filtro `incluir_bajas` opcional).

---

## Scenario: dar de baja una inscripción desde Socio

Given una `Inscripcion Actividad` `Activa` del socio
When Secretaría ejecuta `baja_inscripcion_desk` con `inscripcion` y motivo opcional
Then `Inscripcion Actividad.estado` pasa a `Baja`
And `Socio.actividad` (resumen) se sincroniza
And el socio **no** cambia de estado global (permanece `Activo` salvo otra regla).

---

## Scenario: baja del socio cierra todas las inscripciones activas

Given un `Socio` con dos `Inscripcion Actividad` en estado `Activa`
When Secretaría ejecuta **Dar de baja** sobre el socio
Then ambas inscripciones pasan a `Baja`
And `Socio.actividad` queda vacío
And el socio queda en `estado = Baja`.

---

## Scenario: no duplicar inscripción activa equivalente

Given ya existe inscripción activa socio + actividad + grupo (+ equipo)
When Secretaría intenta inscribir la misma combinación
Then no se crea duplicado (comportamiento actual de `inscribir_socio_selecciones`).

---

## Scenario: socio en Pendiente de Inscripción sin inscripciones

Given `Socio.estado = Pendiente de Inscripción`
And el socio no tiene inscripciones activas
When Secretaría ejecuta **Activar socio** sin inscribir
Then sigue permitido (`activar_socio_manual` actual).

---

## Scenario: acceso restringido

Given usuario sin `Secretaria` / `System Manager`
When invoca APIs de inscripción Desk
Then `PermissionError`.

---

## Scenario: formulario Inscripcion Actividad con cascada actividad → grupo → equipo

Given una `Actividad` con `usa_grupos = 1` y grupos/equipos habilitados
When Secretaría abre o crea `Inscripcion Actividad` y elige la actividad
Then el selector **Grupo / tira** muestra solo grupos de esa actividad
When elige un grupo
Then **Equipo / categoría** muestra solo equipos de ese grupo
And si la actividad no usa grupos, los campos grupo/equipo se ocultan.

---

## Scenario: diálogo Inscribir en actividades (Socio / alta guiada)

Given una `Actividad` con `usa_grupos = 1`
When Secretaría elige la actividad en el diálogo
Then los campos Link **Grupo / tira** y **Equipo / categoría** se muestran
And el autocompletado de grupo solo ofrece `Grupo Actividad` de esa actividad habilitados
When elige un grupo
Then el autocompletado de equipo solo ofrece `Equipo Actividad` de ese grupo habilitados.

---

## Scenario: confirmar inscripción con selección pendiente en el diálogo

Given Secretaría eligió actividad (y grupo/equipo si aplica) en el diálogo «Inscribir en actividades»
And no pulsó «Agregar otra actividad»
When pulsa **Confirmar inscripción**
Then la selección pendiente se incluye y se registra la inscripción
And no se exige un paso previo de «Agregar» para una sola actividad.

---

## Scenario: actividad con grupos exige grupo antes de confirmar

Given una `Actividad` con `usa_grupos = 1`
When Secretaría confirma sin elegir grupo / tira
Then el cliente muestra error claro antes de llamar al servidor
And el servidor rechaza la selección si faltara el grupo.

---

## UI Desk

Given formulario `Socio` con pestaña o sección **Inscripciones**
When hay inscripciones activas
Then cada fila muestra botón **Dar de baja** con confirmación
And botón **Inscribir en actividades** (existente) permanece disponible.

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | extender `activities/services/inscripcion_socio.py` |
| API | `members/api/socio_operaciones_desk.py` |
| UI | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_inscripcion_gestion_desk.py` |
