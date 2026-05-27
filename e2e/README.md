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

## Instalación (una vez, en WSL Ubuntu)

### 1. Node.js en Linux (obligatorio)

En WSL, comprobá:

```bash
which node
which npm
```

Si `which node` **no imprime nada**, o apunta a `/mnt/c/Program Files/...`, tenés el
shim de **Windows** (eso provoca `CMD.EXE` + rutas UNC).

Instalá Node con **nvm** (recomendado):

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 24
nvm use 24
node -v && npm -v
which node   # ej. /home/francisco/.nvm/versions/node/v24.x.x/bin/node
```

Verificación rápida:

```bash
./scripts/check-node-env.sh
```

### 2. Dependencias Playwright (en la app)

```bash
cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
rm -rf node_modules   # si antes instalaste con npm de Windows
npm install
./scripts/install-playwright-browser.sh
```

### Ubuntu 26.04 (u otra distro sin build de Chromium)

Si ves `Playwright does not support chromium on ubuntu26.04`:

```bash
sudo apt update
sudo apt install -y wget
cd /tmp
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
rm -f .pw-browser-ready
./scripts/install-playwright-browser.sh
# crea .pw-channel.env con PW_CHANNEL=chrome
```

Los tests usan Chrome del sistema; no hace falta `playwright install chromium`.

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

### Error `CMD.EXE` / UNC / `EPERM … C:\Windows\test-results`

Suele pasar si corrés `npm` desde **PowerShell/CMD** apuntando a una ruta
`\\wsl.localhost\Ubuntu\...` (Node de Windows, cwd = `C:\Windows`).

**Solución:** terminal **Ubuntu (WSL)**, ruta Linux:

```bash
cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
chmod +x scripts/run-qa-e2e.sh
npm install
npx playwright install chromium
export PLAYWRIGHT_BASE_URL=http://localhost:8000
QA_SUPERVISED=1 ./scripts/run-qa-e2e.sh --headed
# o: QA_SUPERVISED=1 npm run qa:e2e:headed
```

Comprobá: `./scripts/check-node-env.sh` debe decir `OK: node=...`.

Si `which node` está vacío → instalá Node con nvm (sección anterior).
Si apunta a `/mnt/c/...` → es npm de Windows; instalá nvm y rehacé `npm install`.

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
