#!/usr/bin/env bash
# Development setup: installs uv if missing, a uv-managed Python and every
# project dependency into .venv/. No system Python is needed.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo ">> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ">> Installing the uv-managed Python..."
uv python install
echo ">> Creating .venv and installing dependencies..."
uv sync

cat <<MSG

Done. Useful commands:
  uv run arenahub                                        # run the app
  uv run pytest                                          # run the tests
  uv run pyinstaller ArenaHub.spec --clean --noconfirm   # single-file build in dist/
MSG
