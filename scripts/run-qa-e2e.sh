#!/usr/bin/env bash
# Ejecuta Playwright desde el directorio de la app (WSL/Linux).
# Evita que npm de Windows arranque en C:\Windows con rutas UNC \\wsl.localhost\...
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"${ROOT}/scripts/check-node-env.sh"

if [[ -n "${WINDIR:-}" && -z "${WSL_DISTRO_NAME:-}" ]]; then
	echo "ERROR: Parece que estás en CMD/PowerShell de Windows, no en WSL." >&2
	echo "Abrí una terminal Ubuntu (WSL) y ejecutá:" >&2
	echo "  cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management" >&2
	echo "  ./scripts/run-qa-e2e.sh --headed" >&2
	exit 1
fi

if [[ ! -d node_modules/@playwright/test ]]; then
	echo "Instalando dependencias npm…"
	npm install
	"${ROOT}/node_modules/.bin/playwright" install chromium
fi

export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://localhost:8000}"

PW="${ROOT}/node_modules/.bin/playwright"
if [[ ! -x "$PW" ]]; then
	echo "ERROR: no existe $PW — corré: npm install && npx playwright install chromium" >&2
	exit 1
fi

echo "PLAYWRIGHT_BASE_URL=$PLAYWRIGHT_BASE_URL"
echo "cwd=$ROOT"
exec "$PW" test "$@"
