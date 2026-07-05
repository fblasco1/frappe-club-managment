# Spec: Dashboard Gestión de Actividades y Deportes

Panel Desk en el workspace **Gestión de Actividades** (rol `Secretaria`): responde
¿qué tan ocupado está el club? y ¿qué disciplinas rinden mejor?

**Relacionado:** `gestion_actividades_panel.md`, `activities_jerarquia.md`

---

## Scenario: KPIs principales del dashboard

Given Secretaria consulta el dashboard de Gestión de Actividades
Then ve **exactamente tres** cards KPI:
1. **Inscripciones activas** — suma de `Inscripcion Actividad` con `estado = Activa`
2. **Actividad con mayor crecimiento del mes** — disciplina con más altas en el mes y delta vs mes anterior
3. **Actividad con más socios inscriptos** — disciplina con mayor cantidad de socios únicos con inscripción activa
And **no** ve cards de ocupación general ni aptos médicos.

---

## Scenario: total de inscripciones activas

Given existen `Inscripcion Actividad` con `estado = Activa` (un socio puede tener varias)
When Secretaria consulta el dashboard
Then ve la **suma** de inscripciones activas (no socios únicos) en la card KPI
And **Ver más** abre `Inscripcion Actividad` filtrada a `Activa`.

---

## Scenario: porcentaje de ocupación general (solo gráficos)

> La ocupación **no** se muestra como card KPI; solo alimenta el gráfico por deporte/categoría.

Given nodos del catálogo con `capacidad > 0` (Actividad sin grupos, Grupo Actividad o Equipo Actividad)
And inscripciones activas en cada nodo hoja
When Secretaria consulta el dashboard
Then el servicio puede calcular **% ocupación** para gráficos y reportes internos
And **no** aparece como card en el panel.

---

## Scenario: actividad con mayor crecimiento del mes

Given inscripciones con `fecha_inscripcion` en el mes de referencia
When Secretaria consulta el dashboard
Then ve en la card KPI la **actividad** que más inscripciones nuevas sumó en ese mes
And el delta respecto al mes anterior en la misma card.

---

## Scenario: actividad con más socios inscriptos

Given inscripciones activas agrupadas por `actividad`
When Secretaria consulta el dashboard
Then ve la **actividad** con mayor cantidad de **socios únicos** inscriptos
And la cantidad de socios en la card KPI
And **Ver más** abre `Inscripcion Actividad` filtrada a esa actividad y `Activa`.

---

## Scenario: aptos médicos (fuera del dashboard)

> La información de aptos médicos **no** se muestra en este dashboard.

Given socios con inscripción activa y apto vencido o sin fecha
When Secretaria consulta el dashboard de actividades
Then **no** ve card, acción rápida ni enlace de aptos médicos.

---

## Scenario: gráfico ocupación por deporte / categoría

Given inscripciones activas agrupadas por `actividad` y `grupo_actividad` (tira / color)
When Secretaria consulta el dashboard
Then ve un gráfico de barras apiladas con inscriptos por disciplina y segmento de grupo.

---

## Scenario: filtro de actividades en gráfico de ocupación

Given el gráfico de ocupación por deporte / categoría con varias disciplinas
When Secretaria desmarca una o más actividades en el filtro del gráfico
Then esas actividades dejan de mostrarse en el gráfico
And los KPIs y el resto del dashboard no cambian
And la selección se conserva al recargar el panel en la misma sesión.

---

## Scenario: tooltip con composición por actividad

Given una actividad con inscripciones en uno o más grupos / tiras
When Secretaria pasa el cursor sobre la barra de esa actividad
Then el tooltip muestra el título de la actividad y el total de inscriptos
And lista cada grupo / tira con su cantidad y color del segmento
And no incluye grupos con cero inscriptos en esa actividad.

---

## Scenario: color distinto por grupo en gráfico de ocupación

Given una actividad con más de un grupo / tira con inscripciones activas
When Secretaria consulta el gráfico de ocupación
Then cada segmento (grupo) tiene un color asignado de forma estable
And ningún segmento usa el color negro por defecto por falta de paleta.

---

## Scenario: lista de espera top 5

Given `Lista Espera Actividad` con `estado = En espera` en nodos sin cupo disponible
When Secretaria consulta el dashboard
Then ve hasta 5 filas con actividad, grupo/equipo, cantidad en espera y fecha más antigua
And **Ver más** abre la lista filtrada.

---

## Scenario: asistencia promedio por deporte (diferido)

> **Estado:** oculto en UI hasta implementar control de asistencia.

Given `Asistencia Sesion` de las últimas 4 semanas con `inscriptos > 0`
When Secretaria consulta el dashboard
Then **no** ve gráfico ni acción de asistencia en esta versión.

---

## Scenario: catálogo en página separada

Given Secretaria en el workspace Gestión de Actividades
When abre **Catálogo de actividades** desde el sidebar o la acción **Modificar cupos / horarios**
Then navega a la página Desk `/desk/catalogo-actividades`
And el dashboard del workspace **no** incluye el acordeón del catálogo.

---

## Scenario: disponibilidad de infraestructura

Given el módulo de canchas/horarios aún no está modelado
When Secretaria consulta el dashboard
Then la sección de infraestructura muestra estado **próximamente** (`disponible = false`).

---

## Scenario: acciones rápidas

Given Secretaria en el dashboard
When usa las acciones rápidas
Then puede abrir **Inscribir socio a actividad** (lista `Inscripcion Actividad` nueva)
And **Modificar cupos / horarios** (página `catalogo-actividades`).

---

## Scenario: filtros globales

Given Secretaria en el dashboard
When selecciona filtro por **actividad** o **rango de fechas**
Then los KPIs y gráficos se recalculan para ese alcance
And el filtro de sede queda reservado para multi-sede futura (`disponible = false`).

---

## Scenario: buscador universal de socio

Given Secretaria en cualquier pantalla Desk del club con navegación custom
When escribe DNI o apellido en la barra superior
Then ve sugerencias de `Socio` y al elegir una abre su ficha Desk.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta consultar el endpoint del dashboard
Then recibe error de permisos.
