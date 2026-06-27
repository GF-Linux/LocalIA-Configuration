#!/usr/bin/env bash
set -euo pipefail

# Tudo que é pesado vai pro D: (432GB livres). O C: fica intocado.
export HF_HOME=/mnt/d/wsl/hf_cache
export HF_HUB_CACHE=/mnt/d/wsl/hf_cache/hub
export TMPDIR=/mnt/d/wsl/tmp
export FT_ADAPTER_DIR=/mnt/c/Users/jared/Desktop/professor-tutor/fine-tune/outputs/adapter
export FT_OUT_DIR=/mnt/d/professor-ft-out
export PATH="$HOME/.local/bin:$PATH"

mkdir -p "$HF_HUB_CACHE" "$TMPDIR" "$FT_OUT_DIR" /mnt/d/professor-ft-build
cd /mnt/d/professor-ft-build   # llama.cpp clona/builda aqui, no D:

VENV=/home/jared/ft-venv

echo "=== inicio export 14B->GGUF (saida no D:): $(date) ==="
echo "--- disco D: antes ---"; df -h /mnt/d | tail -1
"$VENV/bin/python" "$FT_ADAPTER_DIR/../../export_gguf.py"
echo "=== arquivos GGUF gerados ==="
ls -lh "$FT_OUT_DIR"/*.gguf 2>/dev/null || echo "(nenhum .gguf encontrado)"
echo "--- disco D: depois ---"; df -h /mnt/d | tail -1
echo "=== fim export: $(date) ==="
