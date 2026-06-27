"""Merge do adapter + export GGUF (q4_k_m). Roda na 4080, após train.py.
Usa o utilitário do Unsloth para salvar direto em GGUF.

Caminhos configuráveis por env (default = comportamento do plano):
  FT_ADAPTER_DIR  diretório do adapter LoRA  (default: outputs/adapter)
  FT_OUT_DIR      diretório de saída do GGUF (default: outputs)
Útil para redirecionar a saída pesada (~28GB de merge fp16) para um disco
com espaço, p.ex. FT_OUT_DIR=/mnt/d/professor-ft-out."""
import os
from unsloth import FastLanguageModel

ADAPTER_DIR = os.environ.get("FT_ADAPTER_DIR", "outputs/adapter")
OUT_DIR = os.environ.get("FT_OUT_DIR", "outputs")

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=ADAPTER_DIR, max_seq_length=2048, load_in_4bit=True,
)
model.save_pretrained_gguf(OUT_DIR, tokenizer, quantization_method="q4_k_m")
print(f"GGUF gerado em {OUT_DIR}/ (q4_k_m)")
