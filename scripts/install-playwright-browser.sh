#!/usr/bin/env bash
# Instala el navegador para Playwright o configura Chrome/Chromium del sistema.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PW="${ROOT}/node_modules/.bin/playwright"
ENV_FILE="${ROOT}/.pw-channel.env"

if [[ ! -x "$PW" ]]; then
	echo "ERROR: ejecutá primero: npm install" >&2
	exit 1
fi

_write_channel() {
	local ch="$1"
	echo "export PW_CHANNEL=${ch}" >"$ENV_FILE"
	echo "Navegador: PW_CHANNEL=${ch} (sistema, sin bundle de Playwright)"
}

if "$PW" install chromium 2>/dev/null; then
	rm -f "$ENV_FILE"
	echo "Chromium de Playwright instalado correctamente."
	exit 0
fi

echo "Playwright no publica Chromium para esta distro ($(lsb_release -ds 2>/dev/null || uname -m))."
echo "Probando navegador del sistema…"

if command -v google-chrome-stable >/dev/null 2>&1; then
	_write_channel "chrome"
	exit 0
fi
if command -v google-chrome >/dev/null 2>&1; then
	_write_channel "chrome"
	exit 0
fi
if command -v chromium-browser >/dev/null 2>&1; then
	_write_channel "chrome"
	exit 0
fi
if command -v chromium >/dev/null 2>&1; then
	_write_channel "chrome"
	exit 0
fi

cat >&2 <<'EOF'
No hay navegador usable. Instalá Google Chrome en WSL:

  sudo apt update
  sudo apt install -y wget
  cd /tmp
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt install -y ./google-chrome-stable_current_amd64.deb

Luego volvé a ejecutar:

  ./scripts/install-playwright-browser.sh

EOF
exit 1
