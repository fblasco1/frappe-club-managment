# Spec: navegación Desk en Actividades (tabs + sidebar)

**Relacionado:** `gestion_actividades_dashboard.md`, navegación simétrica a Socio en `club_desk_navigation.js`.

Al abrir el catálogo o fichas List/Form de actividades, Secretaría no debe perder los tabs
club (Socios / Actividades / Tesorería) ni el sidebar de Actividades.

---

## Scenario: Page catálogo mantiene nav de Actividades

Given un usuario con rol `Secretaria` o `System Manager`
When navega a la Page Desk `catalogo-actividades`
Then la ruta se considera página club (`is_club_desk_page`)
And el tab activo es **Actividades**
And se refresca el sidebar de Actividades (link a Gestión de Actividades / Catálogo).

---

## Scenario: Form/List de DocTypes de actividades mantienen nav

Given un usuario con rol `Secretaria` o `System Manager`
When navega a List o Form de `Actividad`, `Grupo Actividad`, `Equipo Actividad` o `Inscripcion Actividad`
Then la ruta se considera página club
And el tab activo es **Actividades**
And se refresca el sidebar de Actividades
And no se ejecuta `clear_mount` de los tabs club.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Nav JS | `public/js/club_desk_navigation.js` |
| Sidebar boot | `public/js/actividades_sidebar_boot.js` |
| Tests | `tests/test_navegacion_actividades_desk.py` |
