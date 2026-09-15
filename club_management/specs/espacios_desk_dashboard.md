# Spec: Desk Espacios — dashboard y navegación

Vista Desk principal de **Gestión de Espacios y Canchas**: dashboard operativo
en `/desk/espacios` (Page), ítem de navbar entre Actividades y Tesorería, y
acceso desde el App Desktop **SICLUB**.

**Roles lectura:** Coordinacion, Secretaria, Tesoreria, System Manager  
**Relacionado:** `spaces_ocupacion_dashboard.md`, `siclub_desktop_app.md`,
`spaces_catalogo_ocupacion.md`

---

## Scenario: hijo Espacios en SICLUB

Given el ícono App **SICLUB**
When se ejecuta `ensure_siclub_desktop_icons`
Then existe un Desktop Icon hijo con `label = "Espacios"`, `parent_icon = "SICLUB"`
And `icon_type = "Link"` y `link_type = "Workspace Sidebar"`
And `link_to` apunta al Workspace Sidebar de Espacios
And el orden de hijos incluye Socios, Actividades, Espacios y Configuración de Sistema

---

## Scenario: navbar «Gestión de Espacios y Canchas»

Given workspaces públicos del club sincronizados
When se consulta el Workspace de espacios
Then su `title` / label visible es **Gestión de Espacios y Canchas**
And su `sequence_id` es **0.3** (después de Gestión de Actividades ~0.15 y antes de Tesorería 0.5)
And es `public` y tiene roles Coordinacion, Secretaria, Tesoreria y System Manager

---

## Scenario: `/desk/espacios` es el dashboard Page

Given Coordinacion (o rol autorizado de Spaces)
When navega a `/desk/espacios`
Then carga la **Page** `espacios` (no solo shortcuts de Workspace)
And ve:
1. listado de **solicitudes de reserva pendientes** (`Reserva Espacio` con `estado = Pendiente`)
2. **actividades del día** ordenadas por hora, con **selector de espacio**
3. acciones del page-head: **Listado de espacios** y **Ocupación de Espacios** (junto a Actualizar; sin CTAs duplicados en el cuerpo)

---

## Scenario: API — reservas pendientes

Given existen `Reserva Espacio` en estado `Pendiente` y otras Confirmada/Cancelada
When un usuario autorizado llama al endpoint del dashboard Desk
Then recibe solo las pendientes (campos útiles: name, espacio, fecha, hora_desde, hora_hasta, tipo, motivo)
And están ordenadas por fecha y hora

---

## Scenario: API — actividades del día filtrables por espacio

Given horarios y/o reservas del día en varios espacios
When consulta el dashboard sin filtro de espacio
Then recibe la agenda del día ordenada por `hora_desde`
When filtra por un `espacio`
Then solo recibe ítems de ese espacio
And un usuario sin roles de Spaces recibe PermissionError

---

## Scenario: Coordinacion home_page

Given el rol `Coordinacion`
When se sincroniza el módulo Espacios
Then `home_page` del rol sigue siendo `/desk/espacios` (la Page dashboard)

---

## Scenario: landing Desk de Coordinacion — solo Espacios

Given un usuario con rol `Coordinacion` (sin System Manager ni Secretaría)
When carga el Desk (`/desk`) / bootinfo
Then `desktop_icons` contiene **únicamente** el ícono **Espacios**
And no aparecen Framework, SICLUB, Calidad u otros apps genéricos
And al abrir Espacios usa Workspace Sidebar `Espacios` (dashboard / ocupación / catálogo)
And Administrator / System Manager **no** reciben este landing filtrado

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/espacios_desk_dashboard.md` |
| Servicio | `spaces/services/espacios_desk_dashboard.py` |
| API | `spaces/api/espacios_desk_dashboard.py` |
| Page | `spaces/page/espacios/` + `public/js/espacios_dashboard_page.js` |
| Workspace | `spaces/workspace/espacios/espacios.json` |
| Sidebar / SICLUB | `spaces/setup/espacios_workspace_sidebar.py`, `siclub_desktop_icon.py` |
| Patch | `patches/v1_0/sync_espacios_desk_dashboard.py` |
| Tests | `spaces/tests/test_espacios_desk_dashboard.py`, `members/tests/test_siclub_desktop_icon.py` |
