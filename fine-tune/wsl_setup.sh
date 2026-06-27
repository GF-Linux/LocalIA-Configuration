#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "=== instalando uv ==="
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== uv ==="
uv --version

VENV=/home/jared/ft-venv
if [ ! -d "$VENV" ]; then
  echo "=== criando venv py3.12 ==="
  uv venv "$VENV" --python 3.12
fi

echo "=== python da venv ==="
"$VENV/bin/python" --version
echo "OK setup base"
