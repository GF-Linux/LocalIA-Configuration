# Professor — Fine-tune (Fatia A: dry-run)

Pipeline de de-risco: dados → ChatML → QLoRA (Qwen2.5-Coder-14B, Unsloth) → GGUF → Ollama → smoke-eval.

## Atribuição
Usa uma amostra do dataset **nvidia/OpenCodeInstruct** (Hugging Face), licença **CC BY 4.0**.
Atribuição: NVIDIA, OpenCodeInstruct, https://huggingface.co/datasets/nvidia/OpenCodeInstruct

## Ambiente
- CPU (data-prep/formatter/eval): `pip install -r requirements.txt`
- GPU (treino, na 4080): ver `requirements-gpu.txt` + model card do Unsloth.
- O treino rodou em **WSL2 Ubuntu** (venv Python 3.12 via `uv`, torch+cu128, Unsloth).
  Os scripts `wsl_*.sh` documentam exatamente como o ambiente foi montado e rodado.

## Pipeline (ordem)
1. `python -m ftlib.collect_seeds`        # valida as sementes de professor
2. `python -m ftlib.collect_oci --n 300`  # baixa amostra do OpenCodeInstruct
3. `python -m ftlib.build_dataset`        # → data/train.jsonl + data/heldout.jsonl (ChatML)
4. `python train.py`                      # QLoRA na 4080 → outputs/adapter
5. `python export_gguf.py`                # → GGUF q4_k_m (merge 16-bit + quantização)
6. `ollama create professor-ft -f Modelfile`
7. `python -m ftlib.smoke_eval`           # roda held-out pelo Ollama, conta JSON válido

## Hardware: redirecionar saída pesada (export do 14B)
O export faz merge do modelo em 16-bit (~28 GB para o 14B) e gera o GGUF — pesado em
RAM e disco. Em máquina com pouca RAM/`C:` apertado, redirecione tudo para um disco
com espaço via env (ver `wsl_export.sh`):

    HF_HOME=/mnt/d/wsl/hf_cache TMPDIR=/mnt/d/wsl/tmp \
    FT_ADAPTER_DIR=<abs>/outputs/adapter FT_OUT_DIR=/mnt/d/professor-ft-out \
    python export_gguf.py

O Unsloth grava o GGUF em `<FT_OUT_DIR>_gguf/` (ex.:
`/mnt/d/professor-ft-out_gguf/qwen2.5-coder-14b-instruct.Q4_K_M.gguf`). Aponte o `FROM`
do Modelfile do `ollama create` para esse arquivo.

## Resultado do dry-run (2026-06-27)
Pipeline validado ponta a ponta com **Qwen2.5-Coder-14B**: treino QLoRA coube na VRAM da
4080 (loss 0.83→0.26, 39 steps); export do GGUF q4_k_m concluído com a saída redirecionada
para o `D:` (host só tem 15.7 GB de RAM). **smoke-eval: 6/6 JSON válido (frac=1.00)** —
critério binário (≥ 0.5) atingido. Qualidade pedagógica e troca do `professor.model` em
produção ficam para a Fatia B.
