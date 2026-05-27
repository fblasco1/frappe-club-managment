# E2E Playwright — Solicitud de Asociación

Pruebas de UI **opcionales** (no corren en el job `tests` de GitHub por defecto).

## Requisitos

- Sitio Frappe arriba (ej. `http://dev.localhost:8000`).
- Usuario Secretaría en el sitio.
- Node 20+.

## Instalación

```bash
cd apps/club_management   # raíz de la app en el bench
npm ci
npx playwright install chromium
```

## Variables

| Variable | Default | Uso |
|----------|---------|-----|
| `PLAYWRIGHT_BASE_URL` | `http://dev.localhost:8000` | URL del sitio |
| `QA_SECRETARIA_EMAIL` | `secretaria@dev.local` | Login Desk |
| `QA_SECRETARIA_PASSWORD` | `Secretaria123!` | Login Desk |
| `QA_SUPERVISED` | — | Si `1`, el test `@supervised` usa `page.pause()` |
| `PW_VIDEO` | — | Si set, graba video |

## Comandos

```bash
# Headless (rápido)
PLAYWRIGHT_BASE_URL=http://dev.localhost:8000 npm run qa:e2e

# Supervisado (ventana visible)
PLAYWRIGHT_BASE_URL=http://dev.localhost:8000 npm run qa:e2e:headed

# UI mode (paso a paso)
PLAYWRIGHT_BASE_URL=http://dev.localhost:8000 npm run qa:e2e:ui

# Pausas manuales en test supervisado
QA_SUPERVISED=1 npm run qa:e2e:headed
```

## CI API (nivel 1)

El flujo completo de negocio corre en:

```bash
bench --site test_site run-tests \
  --module club_management.members.tests.test_flujo_solicitud_completo
```

## Q&A terminal (nivel 2)

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run
```

Ver skill `.cursor/skills/qa-solicitud-supervisada/SKILL.md`.
