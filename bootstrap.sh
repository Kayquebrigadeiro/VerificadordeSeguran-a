#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -t 1 ]]; then
  GREEN=$'\033[0;32m'
  RED=$'\033[0;31m'
  YELLOW=$'\033[0;33m'
  RESET=$'\033[0m'
else
  GREEN=""
  RED=""
  YELLOW=""
  RESET=""
fi

info() { printf '%s[OK]%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%s[AVISO]%s %s\n' "$YELLOW" "$RESET" "$*"; }
fail() {
  printf '%s[ERRO]%s %s\n' "$RED" "$RESET" "$*" >&2
  exit 1
}

case "$(uname -s)" in
  Linux|Darwin) info "Sistema operacional: $(uname -s)" ;;
  *) warn "Sistema não homologado: $(uname -s). Tentando continuar." ;;
esac

command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || fail "Python 3.11 ou superior é obrigatório (encontrado: $(python3 --version))."
info "Python: $(python3 --version)"

if command -v node >/dev/null 2>&1; then
  node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' \
    || fail "Node.js 18 ou superior é necessário para instalar/construir o frontend (encontrado: $(node --version))."
  info "Node.js: $(node --version)"
else
  warn "Node.js não encontrado; instalação e build do frontend serão ignorados."
fi

if [[ ! -x .venv/bin/python ]]; then
  info "Criando ambiente virtual .venv/"
  python3 -m venv .venv
else
  info "Usando ambiente virtual existente .venv/"
fi

.venv/bin/python -m pip install -e '.[test]'

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  npm --prefix frontend ci
  npm --prefix frontend run build
elif command -v node >/dev/null 2>&1; then
  warn "npm não encontrado; instalação e build do frontend serão ignorados."
else
  warn "Frontend não instalado nem compilado."
fi

.venv/bin/verificalab migrate
.venv/bin/verificalab demo
.venv/bin/python -m pytest backend/tests -o addopts='' -ra

printf '%sOK — use: source .venv/bin/activate && verificalab serve%s\n' \
  "$GREEN" "$RESET"
