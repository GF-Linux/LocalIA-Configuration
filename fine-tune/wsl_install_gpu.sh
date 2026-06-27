#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
VENV=/home/jared/ft-venv
PY="$VENV/bin/python"

echo "=== instalando unsloth + trl + datasets (torch CUDA) ==="
uv pip install --python "$PY" unsloth trl datasets

echo "=== verificando torch/CUDA ==="
"$PY" - <<'PYEOF'
import torch
print("torch:", torch.__version__)
print("cuda disponivel:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device:", torch.cuda.get_device_name(0))
    print("vram GB:", round(torch.cuda.get_device_properties(0).total_memory/1e9, 1))
PYEOF

echo "OK gpu install"
