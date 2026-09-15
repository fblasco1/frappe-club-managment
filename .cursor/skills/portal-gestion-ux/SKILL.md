---
name: portal-gestion-ux
description: >-
  Línea UX unificada del portal de gestión Desk (Socios, Actividades, Espacios,
  Tesorería): theme claro, sin recuadro blanco anidado, nav pills, paneles,
  toolbars, selects y dropdowns. Usar al diseñar o tocar UI Desk del club,
  estilos SCSS/JS de workspaces, pages o paneles de gestión.
---

# Portal de gestión — línea UX

Referencia visual canónica: **dashboard Espacios** (`/desk/espacios`).

## Archivos

| Pieza | Path |
|-------|------|
| Theme compartido | `club_management/public/scss/club_portal_theme.scss` |
| Bundle | `club_management/public/scss/club_management.bundle.scss` |
| Activación JS | `club_management/public/js/club_desk_navigation.js` → `apply_portal_theme()` |
| Ejemplo Espacios | `club_management/public/scss/espacios_desk_layout.scss` + `espacios_dashboard_page.js` |

## Reglas (no negociables)

1. **Tema claro** en rutas del portal (`body.club-portal-theme`); no forzar dark mode en gestión.
2. **Sin recuadro blanco Frappe anidado**: `layout-main-section.frappe-card` transparente; el blanco vive solo en paneles/toolbars.
3. **Nav club** (`.club-desk-nav`): franja blanca, tabs **pill**, búsqueda redondeada.
4. **Accent por área** vía modifier en `body`:
   - `club-portal--socios` → azul `#2563eb`
   - `club-portal--actividades` → verde `#059669`
   - `club-portal--espacios` → teal `#0f766e`
   - `club-portal--tesoreria` → ámbar `#b45309`
5. Controles (`select`/`input`/`date`): borde gris, radius 8px, foco con ring del accent; selects con chevron custom.
6. Dropdowns Desk: menú radius 10px, hover con `--club-accent-soft`.

## Clases utilitarias

Usar estas clases en markup nuevo (no reinventar):

- `.club-portal-toolbar` — filtros / acciones superiores
- `.club-portal-field` + `label` uppercase muted
- `.club-portal-panel` + `.club-portal-panel-title`
- `.club-portal-chip` — badge (día, estado)
- `.club-portal-cta-row` — fila de botones

Tokens CSS (en `body.club-portal-theme`):

- `--club-accent`, `--club-accent-soft`, `--club-accent-hover`, `--club-accent-ink`
- `--club-radius` (10px), `--club-shadow`, `--club-shadow-lg`
- `--bg-color` `#f3f4f6`, `--fg-color` `#ffffff` (superficie Frappe), `--subtle-fg` `#f3f4f6` (header de listas), `--border-color`, `--text-muted`, `--heading-color`

**Importante:** en Frappe Desk, `--subtle-fg` y `--fg-color` son **fondos**, no color de texto. No asignarles grises oscuros.

## Flujo al tocar UI

1. Leer este skill.
2. Si es pantalla nueva del portal: markup con utilidades + accent automático (la nav ya setea el modifier).
3. Estilos específicos del módulo en su SCSS; **reutilizar tokens**, no hardcodear colores de área salvo charts.
4. `bench build --app club_management` + `clear-cache` tras SCSS/JS.
5. Verificar Socios / Actividades / Espacios / Tesorería: mismo canvas gris, mismos controles, accent distinto.

## Anti-patrones

- Volver a pintar `layout-main-section` como card blanca grande
- Cards con multi-shadow / glow / purple gradients
- Selects nativos sin estilo compartido
- Dark mode forzado en páginas de gestión
- Duplicar reglas de nav/flatten fuera de `club_portal_theme.scss`

## Checklist rápido

- [ ] `body` tiene `club-portal-theme` + `club-portal--{área}` en la ruta
- [ ] Contenido en paneles/toolbars blancos sobre fondo gris
- [ ] Foco de inputs usa accent del área
- [ ] Botón primario usa `--club-accent`
- [ ] Assets rebuilded
