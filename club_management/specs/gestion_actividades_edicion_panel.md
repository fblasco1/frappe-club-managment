# Spec: Edición y baja lógica en panel Gestión de Actividades

Complementa `gestion_actividades_panel.md` con **editar** y **deshabilitar** actividades, grupos y equipos desde el workspace.

**Ya implementado:** `get_catalog`, `create_actividad`, `create_grupo`, `create_equipo`, `set_arancel`.

---

## Scenario: editar metadatos de actividad desde panel

Given una `Actividad` existente en el catálogo
When Secretaría llama `update_actividad_desk` con `name`, `titulo`, `usa_grupos`, `habilitada`, `orden`, `descripcion`
Then persisten los cambios
And si `usa_grupos` pasa de 0 a 1, la actividad puede quedar sin grupos hasta que se creen
And si `usa_grupos` pasa de 1 a 0, validar que no haya inscripciones activas con grupo (error o bloqueo).

---

## Scenario: editar grupo / tira

Given un `Grupo Actividad` existente
When Secretaría llama `update_grupo_desk` con `name`, `titulo`, `orden`, `habilitada`
Then persisten los cambios
And el `name` del documento sigue el patrón `{actividad} / {titulo}` (renombrar si cambia título — o prohibir cambio de título y solo orden/flags).

**Decisión:** si cambia `titulo`, ejecutar rename vía Frappe `rename_doc` para mantener convención de nombre.

---

## Scenario: editar equipo

Given un `Equipo Actividad` existente
When Secretaría llama `update_equipo_desk` con `titulo`, `orden`, `habilitada`
Then persisten los cambios con misma regla de rename.

---

## Scenario: deshabilitar nodo sin eliminar

Given actividad habilitada sin inscripciones activas (o con política: permitir deshabilitar igual)
When Secretaría setea `habilitada = 0`
Then deja de aparecer en `get_catalog` (filtro actual)
And no aparece en listas de inscripción Desk / portal
And el registro permanece en base para historial.

---

## Scenario: deshabilitar actividad con inscripciones activas

Given inscripciones `Activa` a esa actividad
When Secretaría intenta `habilitada = 0`
Then error de validación con mensaje claro (o warning + confirmación en UI).

---

## Scenario: abrir formulario Desk desde panel

Given una fila en el panel
When Secretaría hace clic en **Abrir en Desk**
Then navega al formulario estándar del DocType correspondiente.

---

## Scenario: selector de ítem ERPNext para arancel

Given edición inline de arancel
When Secretaría abre el campo ítem
Then muestra Link / autocomplete a `Item` filtrado (`is_stock_item = 0`, grupo ICDPE)
And no exige tipear `item_code` a mano.

---

## Scenario: arancel en actividad con grupos

Given actividad `usa_grupos = 1` con al menos un grupo
When se muestra en panel
Then el arancel inline de la **actividad** se oculta (regla actual)
And cada **grupo** muestra su arancel inline
And cada **equipo / categoría** también muestra inputs de ítem y tarifa (además del resumen efectivo).

---

## Jerarquía «Formativas — Tira Azul»

No se agrega nivel intermedio en v1. Secretaría usa `titulo` del `Grupo Actividad` libre (ej. «Formativas — Tira Azul»).

**Iteración 2 (spec aparte si se requiere):** `parent_grupo` en `Grupo Actividad` para subgrupos anidados.

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | extender `activities/services/gestion_actividades_panel.py` |
| API | extender `activities/api/gestion_actividades_workspace.py` |
| UI | extender `public/js/gestion_actividades_workspace_panel.js` |
| Tests | extender `activities/tests/test_gestion_actividades_panel.py` |
