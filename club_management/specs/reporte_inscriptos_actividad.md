# Spec: Reporte Inscriptos por Actividad

Secretaría / coordinación necesita **emitir un listado** de socios inscriptos en una
actividad (o grupo/equipo) para entregárselo al entrenador.

**Problema Desk:** en la lista `Inscripcion Actividad` el Link `Socio` muestra solo el
número (`title_field = numero_socio`). La columna **Equipo / categoría** ya incluye la
ruta útil (p. ej. `Futbol / TABI B`); Actividad y Grupo / tira sirven para **filtrar**,
no para repetirse en el reporte visual.

**Relacionado:** `inscripcion_gestion_desk.md`, `equipo_actividad_form_roster.md`,
`navegacion_actividades_desk.md`

---

## Scenario: columnas del reporte visual (entrenador)

Given inscripciones activas en una actividad con equipo
When se ejecuta el Script Report **Inscriptos por Actividad** filtrado por esa actividad
Then cada fila incluye:
- `nro_socio` (número / `Socio.name`)
- `nombre` = «Apellido, Nombre» (`format_socio_nombre_completo`)
- `equipo_categoria` = nombre del `Equipo Actividad` si hay; si no, del `Grupo Actividad`;
  si no, título de la `Actividad`
- `estado`
And **no** hay columnas de resultado `actividad` ni `grupo_actividad` (evitan redundancia
con `equipo_categoria`).

---

## Scenario: filtros del reporte

Given el reporte **Inscriptos por Actividad**
Then expone filtros Link: `actividad`, `grupo_actividad`, `equipo_actividad`
And filtro Select `estado` con default `Activa`
And el filtro de grupo se acota a la actividad elegida
And el filtro de **Equipo / categoría** se acota a la actividad elegida (vía grupos de esa
actividad); si además hay grupo, solo equipos de ese grupo.

---

## Scenario: botón Generar reporte

Given el Script Report **Inscriptos por Actividad** abierto en Desk
Then la acción primaria de la página es **Generar reporte**
When el usuario la pulsa con actividad elegida
Then se refresca el informe con los filtros actuales.

---

## Scenario: lista Desk Inscripcion Actividad alineada

Given el DocType `Inscripcion Actividad`
Then `socio_nombre` (Data, solo lectura) está en list view y se sincroniza desde el socio
And `actividad` y `grupo_actividad` tienen `in_standard_filter` y **no** `in_list_view`
And `equipo_actividad` y `estado` siguen en list view
And el Link `socio` permanece en list view (número de socio).

---

## Scenario: acceso

Given usuario sin rol `Secretaria` ni `System Manager`
When ejecuta el reporte
Then `PermissionError` (o el reporte no está permitido por roles del Report).

---

## Scenario: enlace en sidebar Actividades

Given el workspace sidebar **Gestión de Actividades** (boot JS `actividades_sidebar_boot.js`
y sync servidor)
Then en la sección Informes hay un link al Report **Inscriptos por Actividad**.
