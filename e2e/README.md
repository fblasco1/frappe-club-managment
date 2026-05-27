# E2E Playwright — Solicitud de Asociación

Pruebas de UI **opcionales** (no corren en el job `tests` de GitHub por defecto).

## Dónde ejecutar (importante)

| Entorno | ¿Playwright? | Alternativa |
|---------|----------------|-------------|
| **Host (WSL / Windows)** con Docker exponiendo `:8000` | **Sí** (recomendado) | — |
| Contenedor `frappe` (`docker exec … bash`) | **No** | `bench execute …run_supervised` o tests bench |

Dentro del contenedor suele fallar con `playwright: not found` (falta `npm install`) o
`libatk-bridge-2.0.so.0` / `ECONNREFUSED 127.0.0.1:8000` (el HTTP no escucha ahí).

## Requisitos

- Stack Docker levantado y sitio accesible desde el **host**: `http://localhost:8000` o `http://dev.localhost:8000`.
- Usuario Secretaría en el sitio.
- Node 20+ en el **host** (no hace falta dentro del contenedor).

## Instalación (una vez, en el host)

Desde la carpeta de la app en tu máquina (no dentro de `docker exec`):

```bash
cd development/frappe-bench/apps/club_management   # ruta en el repo infra
npm install
npx playwright install chromium
```

Si ves `playwright: not found`, usá los scripts npm (ya llaman `npx playwright`) o ejecutá
`npm install` antes.

## Variables

| Variable | Default | Uso |
|----------|---------|-----|
| `PLAYWRIGHT_BASE_URL` | `http://dev.localhost:8000` | URL del sitio |
| `QA_SECRETARIA_EMAIL` | `secretaria@dev.local` | Login Desk |
| `QA_SECRETARIA_PASSWORD` | `Secretaria123!` | Login Desk |
| `QA_SUPERVISED` | — | Si `1`, el test `@supervised` usa `page.pause()` |
| `PW_VIDEO` | — | Si set, graba video |

## Comandos (desde el host)

```bash
export PLAYWRIGHT_BASE_URL=http://localhost:8000
export QA_SECRETARIA_EMAIL=secretaria@dev.local
export QA_SECRETARIA_PASSWORD=Secretaria123!

# Headless (rápido)
npm run qa:e2e

# Supervisado (ventana visible — requiere display en el host)
QA_SUPERVISED=1 npm run qa:e2e:headed

# UI mode (paso a paso)
npm run qa:e2e:ui
```

En WSL, si `dev.localhost` está en `/etc/hosts`, podés usar
`PLAYWRIGHT_BASE_URL=http://dev.localhost:8000` en lugar de `localhost`.

## CI API (nivel 1)

El flujo completo de negocio corre en:

```bash
bench --site test_site run-tests \
  --module club_management.members.tests.test_flujo_solicitud_completo
```

## Q&A terminal (nivel 2) — dentro del contenedor

```bash
docker exec -it devcontainer-example-frappe-1 bash
cd /workspace/development/frappe-bench
bench --site dev.localhost execute club_management.members.qa.run_supervised.run
```

Ver skill `.cursor/skills/qa-solicitud-supervisada/SKILL.md`.
