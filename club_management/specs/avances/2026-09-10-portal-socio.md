# Avance 2026-09-10 — Portal del Socio (freeze + gate de release)

**Fecha:** 2026-09-10  
**Proyecto:** ICDPE / club_management + landing pedro-echague  
**Autores de sesión:** Cursor + Francisco

---

## Resumen ejecutivo

Se congeló la **Fase B del Portal del Socio** (perfil, proxy de foto, API de sesión + shell Next.js), se validó UAT local, se publicó `develop` en GitHub y se dejó documentado el **gate de release a producción**: no sale Spaces+portal a prod hasta tener reservas externas y desde portal; después va Supervielle sandbox.

---

## 1. Backend (`frappe-club-managment` / `club_management`)

| Acción | Detalle |
|--------|---------|
| Rama feature | `feat/bl6-portal-socio` |
| Commits portal | `ba42f95` (inscripción/sesión) · `f35f5e8` (perfil + proxy foto + API sesión) · `3402fe5` (CORS fail-closed + tipos inscripción catálogo) |
| Merge local | Fast-forward a `develop` |
| Divergencia remote | `origin/develop` tenía squash PR #1 (`e113453`); se resolvió con `merge -s ours` (`cf23c6e`) |
| Push | **`origin/develop` = `29bba4a`** (up to date) |
| Stash intacto | `stash@{0}` cobranza/Spaces/Supervielle (fuera del freeze portal) |

### Tests
- `test_portal_socio_perfil` — 15 OK  
- `test_portal_socio_inscripcion` — 24 OK  
- `test_portal_socio_url` — 7 OK  
- **Total 46/46** en `dev.localhost`

### Config local (`dev.localhost`)
- `portal_socio_url` (site_config): `http://localhost:3000/socios/actividades`
- Club Settings (prod URL): `https://www.icdpedroechague.com.ar/socios/actividades`
- CORS allowlist: `localhost:3000`, `127.0.0.1:3000`, www/apex ICDPE, preview Vercel documentado  
- Catálogo: flags `tipo_inscripcion_portal` / `portal_socio_elige` cargados (deporte / variante_grupo / plana)

---

## 2. Frontend (`pedro-echague-landing-page`)

| Acción | Detalle |
|--------|---------|
| Rama | **`feat/portal-socio`** → `origin/feat/portal-socio` |
| Commits | `9e56afa` shell UI + BFF · `6a6dfaf` tipado tab Deudas |
| `main` | Alineado a `origin/main` (sin los commits del portal) |
| Build | `npm run build` OK (Next 15.2.8) |

### Qué incluye el feature (sí va en el PR)
- Rutas `app/socios/*` (login, inicio, perfil, actividades)
- BFF `app/api/socios/*` (login, logout, perfil, foto, catálogo, inscripciones, contexto, confirmar)
- `components/portal/*` (shell con tabs)
- `lib/frappe/socio-session.ts` (cookies `socio_sid` / `socio_csrf`)
- `conditional-header.tsx`: **oculta el header del sitio marketing** dentro de `/socios` (el portal tiene su propio chrome)

### Qué NO está en el PR (y se mencionó por error como “cambios”)
Había WIP **sin commit** en `header.tsx` y `menu-desplegable.tsx` (link “Portal del socio” en el menú del sitio público).  
Al resetear `main` a `origin/main` ese WIP **se descartó**.  
**No afecta** al portal autenticado: el acceso es `/socios/login`; el header marketing se oculta vía `conditional-header`.  
Si se quiere el link en el menú hamburguesa del sitio, hay que rearmarlo en un commit aparte.

### PR
- Crear/actualizar PR desde: https://github.com/fblasco1/pedro-echague-landing-page/compare/main...feat/portal-socio  
- Título sugerido: `feat(portal): shell del socio (sesión, perfil, actividades) y BFF`
- Ver descripción completa abajo §5.

---

## 3. Smoke UAT local (PASS)

| Paso | Resultado |
|------|-----------|
| Login BFF + cookies `socio_sid`/`socio_csrf` | PASS |
| Inicio + foto vía proxy | PASS |
| Edición teléfono/domicilio + persistencia DB | PASS |
| Rechazo DNI/email/estado (`417 ValidationError`) | PASS |
| Catálogo actividades (deporte/variante/plana) | PASS |
| CORS `Origin: http://localhost:3000` | PASS |

Usuario QA: `socio.portal.qa@icdpe.test`  
Next: `http://localhost:3000` · Frappe: `http://localhost:8000` (Host `dev.localhost`)

---

## 4. Gate de release (backlog actualizado)

**No hay release a producción** de “Spaces + portal socio base” hasta cerrar:

1. **SP-3** — reservas online **externas** (+ comprobante + confirmación Coordinación)  
2. **SP-7** — reservas desde **portal socio**  
3. Portal socio base (ya en `develop` / landing feat) + dual-deploy

**Release siguiente (después del gate):** sandbox Supervielle — botón de pago + débito automático (sin SIRO).

Documento: `club_management/specs/backlog_implementacion.md` (sección “Próximo release a producción”).

---

## 5. Texto sugerido para el PR de la landing

**Título:** `feat(portal): shell del socio (sesión, perfil, actividades) y BFF`

**Body:**

```markdown
## Summary
- Shell del Portal del Socio en Next.js: login, inicio, mis datos, actividades y placeholder de deudas.
- BFF `/api/socios/*` hacia Frappe con cookies `socio_sid` / `socio_csrf`.
- Header del sitio marketing oculto en rutas `/socios` (chrome propio del portal).

## Alcance
- `app/socios/*`, `app/api/socios/*`, `components/portal/*`, `lib/frappe/socio-session.ts`
- No incluye Spaces, Supervielle ni link de menú marketing al portal.

## Test plan
- [ ] `npm run build`
- [ ] Login local con socio QA → cookies de sesión
- [ ] Inicio + foto proxy
- [ ] Editar teléfono/domicilio; DNI/email/estado rechazados
- [ ] Catálogo actividades por deporte/variante/plana
- [ ] Env prod: `FRAPPE_BASE_URL=https://gestion.icdpedroechague.com.ar`

## Nota de release
Sale a Vercel junto con backend en Hetzner **después** del gate Spaces (reservas externas + portal).
```

---

## 6. Pendientes inmediatos

- [ ] Abrir PR landing `feat/portal-socio` → `main` con la descripción de §5 (`gh` requiere login)
- [ ] (Opcional) Link “Portal del socio” en menú del sitio
- [ ] Implementar SP-3 + SP-7 (gate)
- [ ] Deploy dual solo al cerrar el gate
- [ ] Luego: sandbox Supervielle (botón pago + débito automático)
