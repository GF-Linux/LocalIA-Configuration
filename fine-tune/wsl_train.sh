#!/usr/bin/env bash
set -euo pipefail

cd /mnt/c/Users/jared/Desktop/professor-tutor/fine-tune
export PATH="$HOME/.local/bin:$PATH"
export HF_HUB_ENABLE_HF_TRANSFER=1
VENV=/home/jared/ft-venv

echo "=== inicio treino: $(date) ==="
"$VENV/bin/python" train.py
echo "=== fim treino: $(date) ==="
