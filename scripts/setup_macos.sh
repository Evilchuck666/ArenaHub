#!/usr/bin/env bash
# Instala uv (si falta), Python y todas las dependencias del proyecto.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo ">> Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ">> Instalando Python gestionado por uv..."
uv python install
echo ">> Creando .venv e instalando dependencias..."
uv sync

cat <<MSG

Listo. Comandos útiles:
  uv run arenahub                                   # ejecutar la app
  uv run pyinstaller ArenaHub.spec --clean --noconfirm   # binario onefile en dist/
MSG
