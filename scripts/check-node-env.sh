#!/usr/bin/env bash
# Verifica que Node/npm sean binarios Linux (no shims de Windows en WSL).
set -euo pipefail

_fail() {
	echo "ERROR: $1" >&2
	echo "" >&2
	echo "$2" >&2
	exit 1
}

if [[ -z "${WSL_DISTRO_NAME:-}" ]] && [[ "$(uname -s 2>/dev/null)" != "Linux" ]]; then
	_fail "Entorno no Linux/WSL" "Usá una terminal Ubuntu (WSL), no CMD/PowerShell."
fi

NODE_PATH="$(command -v node 2>/dev/null || true)"
NPM_PATH="$(command -v npm 2>/dev/null || true)"

if [[ -z "$NODE_PATH" ]]; then
	_fail "No hay 'node' en PATH (Linux)" "$(cat <<'EOF'
Instalá Node 20+ en WSL, por ejemplo con nvm:

  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  source ~/.bashrc
  nvm install 24
  nvm use 24
  node -v && npm -v

Luego en la app:
  cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
  rm -rf node_modules
  npm install
  npx playwright install chromium
EOF
)"
fi

case "$NODE_PATH" in
	/mnt/c/*|*.exe) ;;
	*)
		echo "OK: node=$NODE_PATH ($(node -v 2>/dev/null || echo '?'))"
		exit 0
		;;
esac

_fail "Node/npm de Windows detectado en WSL" "$(cat <<EOF
  node → $NODE_PATH
  npm  → ${NPM_PATH:-?}

Eso invoca CMD.EXE y falla con rutas UNC.

1) Instalá Node **dentro** de Ubuntu (nvm recomendado):

  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  source ~/.bashrc
  nvm install 24
  hash -r
  which node   # debe ser ~/.nvm/... no /mnt/c/...

2) Reinstalá dependencias del proyecto:

  cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
  rm -rf node_modules
  npm install
  npx playwright install chromium
EOF
)"
