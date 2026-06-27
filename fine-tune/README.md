# Professor — Fine-tune (Fatia A: dry-run)

Pipeline de de-risco: dados → ChatML → QLoRA (Qwen2.5-Coder-14B, Unsloth) → GGUF → Ollama → smoke-eval.

## Atribuição
Usa uma amostra do dataset **nvidia/OpenCodeInstruct** (Hugging Face), licença **CC BY 4.0**.
Atribuição: NVIDIA, OpenCodeInstruct, https://huggingface.co/datasets/nvidia/OpenCodeInstruct

## Ambiente
- CPU (data-prep/formatter/eval): `pip install -r requirements.txt`
- GPU (treino, na 4080): ver `requirements-gpu.txt` + model card do Unsloth.

## Pipeline (ordem)
1. `python -m ftlib.collect_seeds`        # valida as sementes de professor
2. `python -m ftlib.collect_oci --n 300`  # baixa amostra do OpenCodeInstruct
3. `python -m ftlib.build_dataset`        # → data/train.jsonl + data/heldout.jsonl (ChatML)
4. `python train.py`                      # QLoRA na 4080 → outputs/adapter
5. `python export_gguf.py`                # → outputs/professor-ft.gguf
6. `ollama create professor-ft -f Modelfile`
7. `python -m ftlib.smoke_eval`           # roda held-out pelo Ollama, conta JSON válido
