# Spec: Ícono Desk SICLUB (menú de apps)

**Relacionado:** landing Secretaría (`club_desktop_landing.py`), branding `login_siclub_branding.md`  
**Módulo:** `members/setup/`

En el escritorio Desk (junto a Framework / carpetas ERPNext), debe existir un ícono de app **SICLUB**.
Al tocarlo debe comportarse como **Framework**: abrir el modal con los workspaces/accesos
equivalentes a lo que ve Secretaría en su landing.

---

## Scenario: ícono App SICLUB visible para Administrator / System Manager

Given un usuario con permiso de app club (`has_app_permission`)
When carga `/desk`
Then existe un `Desktop Icon` con `label = "SICLUB"`, `icon_type = "App"`, `app = "club_management"`
And no está `hidden`

---

## Scenario: clic en SICLUB muestra accesos de Secretaría

Given el ícono App **SICLUB**
When el usuario lo abre (modal como Framework)
Then ve hijos con `parent_icon = "SICLUB"`:
- **Socios** → sidebar con el mismo contenido operativo de Secretaría
- **Actividades** → sidebar de Gestión de Actividades
- **Configuración de Sistema** → acceso a `Club Settings`
And cada hijo es `icon_type = "Link"` y `link_type = "Workspace Sidebar"`

---

## Scenario: Secretaría sigue con landing filtrado

Given un usuario con rol `Secretaria` (no Administrator)
When carga Desk
Then sigue viendo el landing sintético de 3 íconos (Socios / Actividades / Configuración)
And no se exige que use el ícono App SICLUB (el landing ya reemplaza el menú completo).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Setup | `members/setup/siclub_desktop_icon.py` |
| Patch | `patches/v1_0/ensure_siclub_desktop_icon.py` |
| Tests | `members/tests/test_siclub_desktop_icon.py` |
