# Spec: formulario Equipo Actividad — layout y roster de socios

**Relacionado:** `activities_jerarquia.md`, `inscripcion_gestion_desk.md`

---

## Scenario: Grupo / tira y Equipo / categoría en la misma fila

Given el formulario Desk `Equipo Actividad`
Then **Grupo / tira** (`grupo_actividad`) y **Equipo / categoría** (`titulo`) se muestran en la **misma fila**.

---

## Scenario: roster de socios del equipo

Given inscripciones activas en este `Equipo Actividad`
When Secretaría abre el formulario del equipo guardado
Then debajo aparece una tabla de socios con inscripción activa **en ese equipo**
And columnas: ID (Socio), Nombre, Apellido, DNI, Teléfono móvil, Últ. fecha pago
And **Últ. fecha pago** es la `posting_date` más reciente de un `Payment Entry` submitted contra facturas del socio (vacío si no hay pagos o sin ERPNext).

---

## Scenario: roster por grupo si aún no hay equipo guardado

Given un `Equipo Actividad` nuevo sin `name` (sin guardar)
And `grupo_actividad` seteado
When Secretaría visualiza el formulario
Then la tabla lista socios con inscripción activa en ese **grupo / tira** (cualquier equipo).

---

## Scenario: acceso restringido

Given usuario sin rol `Secretaria` / `System Manager`
When invoca la API de roster
Then `PermissionError`.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `activities/services/inscripcion_actividad_roster.py` |
| API | `activities/api/equipo_actividad_desk.py` |
| Layout JSON | `activities/doctype/equipo_actividad/equipo_actividad.json` |
| UI | `activities/doctype/equipo_actividad/equipo_actividad.js` |
| Tests | `activities/doctype/equipo_actividad/test_equipo_actividad.py` |
