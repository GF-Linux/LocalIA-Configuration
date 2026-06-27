"""QLoRA dry-run: Qwen2.5-Coder-14B com Unsloth. Roda na 4080.
Antes de rodar: descarregue modelos do Ollama (libera VRAM):  ollama stop qwen3:14b
Se o 14B não couber, troque BASE_MODEL pelo 7B (ver README) — resto inalterado."""
import json
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

BASE_MODEL = "unsloth/Qwen2.5-Coder-14B-Instruct"  # fallback: ...-7B-Instruct
MAX_SEQ = 2048

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL, max_seq_length=MAX_SEQ, load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
)

ds = load_dataset("json", data_files="data/train.jsonl", split="train")
def to_text(ex):
    return {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False)}
ds = ds.map(to_text)

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=ds,
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=MAX_SEQ,
        per_device_train_batch_size=1, gradient_accumulation_steps=8,
        num_train_epochs=1, learning_rate=2e-4, logging_steps=5,
        output_dir="outputs/ckpt", optim="adamw_8bit", seed=42,
    ),
)
trainer.train()
model.save_pretrained("outputs/adapter")
tokenizer.save_pretrained("outputs/adapter")
print("adapter salvo em outputs/adapter")
