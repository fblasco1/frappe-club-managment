# Portal socio — inscripción post-pago (Vercel + API Frappe)

**Backlog:** BL-6  
**Relacionado:** `activities_modulo.md`, `activities_jerarquia.md`, `inscripcion_gestion_desk.md`

---

## Arquitectura objetivo

| Capa | Rol |
|------|-----|
| **Frontend** | Sitio del club en **Vercel** (página pública del socio, branding ICDPE). |
| **Backend** | Frappe/ERPNext en Hetzner (`gestion.icdpedroechague.com.ar`) — catálogo, inscripciones, estados de socio. |
| **Integración** | APIs `@frappe.whitelist(allow_guest=True)` con `pago_token` firmado (mismo mecanismo que pago stub / solicitud). |

La página legacy en Frappe (`/inscripcion-actividades`) es **provisional** para desarrollo y QA. El producto final vive en el sitio del club en Vercel y consume las mismas APIs.

### Flujo

1. Socio completa solicitud / pago → recibe `pago_token` y URL de inscripción (dominio del club en Vercel).
2. Vercel llama `get_catalogo_inscripcion_portal` (o endpoints granulares) con el token.
3. Socio elige actividades según reglas de negocio (ver abajo).
4. Vercel llama `confirmar_inscripcion_actividades` con `selecciones`.
5. Frappe crea `Inscripcion Actividad`, actualiza `Socio.estado` y resumen `Socio.actividad`.

### Requisitos técnicos Vercel ↔ Frappe

- CORS en el sitio Frappe para el origen del club (Vercel).
- Rate limit en confirmación (ya existe en API).
- Token no enumerable; errores genéricos ante token inválido.
- `inscripcion_url` en respuestas de pago debe apuntar al **dominio Vercel** (configurable en Club Settings o site config).

---

## Reglas de negocio — qué elige el socio

No hay cascada única «actividad → tira → equipo» para todo. Depende del **tipo de actividad**:

| Tipo | Ejemplos | Portal (socio) | Secretaría (Desk) |
|------|----------|----------------|-------------------|
| **Plana** | Zumba, Ritmos Latinos | Solo **actividad** | — |
| **Deporte** | Basquet, Fútbol, Voley | Solo **actividad** | Asigna **grupo/tira** y **equipo** al validar el alta |
| **Variante de grupo** | Funcional 1 clase/semana, Gimnasia 2 clases, escuelita no competitiva | **Actividad + grupo** (el grupo es el plan/arancel) | No asigna tira/equipo deportivo |

**El socio nunca elige tira deportiva ni categoría U11/U13 en el portal.** Eso lo carga Secretaría cuando valida el alta del deportista.

### Metadata propuesta (implementación futura)

Campo en **`Actividad`** (Select): `tipo_inscripcion_portal`

| Valor | Comportamiento portal |
|-------|------------------------|
| `plana` | Default si `usa_grupos = 0`. Solo nombre de actividad. |
| `deporte` | Solo actividad. Inscripción sin `grupo_actividad` / `equipo_actividad` → pendiente de asignación Desk. |
| `variante_grupo` | Actividad + selector de **Grupo Actividad** cuyos grupos tengan `portal_socio_elige = 1`. |

Campo en **`Grupo Actividad`** (Check): `portal_socio_elige` — solo grupos marcados aparecen en el selector del portal (ej. «1 clase por semana», escuelita recreativa).

---

## Scenario: deporte — socio elige solo Basquet

Given `Actividad` «Basquet» con `tipo_inscripcion_portal = deporte`
When el socio confirma inscripción desde Vercel con `selecciones = [{ "actividad": "Basquet" }]`
Then se crea `Inscripcion Actividad` **sin** `grupo_actividad` ni `equipo_actividad` (o estado «Pendiente asignación»)
And `Socio.estado` pasa a `Activo` (o permanece pendiente según flujo de validación acordado con Secretaría)
And Secretaría completa tira y equipo desde Desk al validar el alta.

---

## Scenario: variante — Funcional 1 clase por semana

Given `Actividad` «Funcional» con `tipo_inscripcion_portal = variante_grupo`
And `Grupo Actividad` «1 clase por semana» con `portal_socio_elige = 1`
When el socio elige actividad y grupo en Vercel
Then la inscripción queda con actividad + grupo y arancel del ítem del grupo
And no se exige equipo.

---

## Scenario: actividad plana — Zumba

Given `Actividad` «Zumba» con `usa_grupos = 0`
When el socio elige solo «Zumba»
Then inscripción con arancel de `Actividad.item`.

---

## Scenario: API catálogo para Vercel

Given token de pago válido
When Vercel llama al catálogo de inscripción
Then recibe actividades habilitadas con `tipo_inscripcion_portal`
And para `variante_grupo` incluye lista de grupos con `portal_socio_elige = 1`
And **no** expone equipos deportivos al socio (endpoint equipos solo Desk / futuro admin).

---

## Scenario: confirmación con token inválido

Given token expirado o manipulado
When Vercel llama `confirmar_inscripcion_actividades`
Then respuesta 404 / error genérico sin filtrar datos de otros socios.

---

## APIs existentes (base)

| Método | Uso portal Vercel |
|--------|-------------------|
| `club_management.activities.api.inscripcion_publica.get_actividades_inscripcion` | Catálogo actividades (ampliar con `tipo_inscripcion_portal`) |
| `club_management.activities.api.inscripcion_publica.get_grupos_actividad` | Solo si `variante_grupo`; filtrar por `portal_socio_elige` |
| `club_management.activities.api.inscripcion_publica.confirmar_inscripcion_actividades` | Confirmar con `selecciones` JSON |
| `club_management.activities.api.inscripcion_publica.get_equipos_grupo` | **No usar en portal socio** — solo Desk |

---

## Fuera de alcance BL-6

- Portal autenticado del socio (carnet, historial de pagos).
- Cambio de inscripciones post-alta desde el sitio del club.
- SIRO / pago online real en Vercel (sprint pagos).
- Implementación del frontend Vercel (repo aparte); este spec define contrato API y reglas Frappe.

---

## Artefactos previstos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/portal_socio_inscripcion.md` (este archivo) |
| API | `activities/api/inscripcion_publica.py` |
| Servicios | `activities/services/actividades_catalog.py`, `grupos_portal.py`, `inscripcion_socio.py` |
| Desk | Completar tira/equipo en `inscripcion_gestion_desk.md` |
| Tests | `activities/tests/test_inscripcion_post_pago.py`, nuevos escenarios portal deporte/variante |
| Legacy UI | `www/inscripcion-actividades.html` — mantener solo para QA hasta cutover Vercel |
