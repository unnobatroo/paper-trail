# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "trl>=0.21",
#   "peft>=0.17",
#   "transformers==5.17.0",
#   "torch==2.14.0",
#   "accelerate==1.15.0",
#   "datasets==5.0.1",
#   "huggingface_hub>=1.0",
# ]
# ///
"""lora fine-tune of the extraction model on our reviewed pages, merged, private repo

runs as an hf job (needs HF_TOKEN). the dataset is build_dataset.py output pushed to a
private hf dataset repo. after this: awq_job.py on OUT_REPO, then eval_extraction with
--baseline against the current model. it ships only if the holdout recall goes up

  hf jobs uv run --flavor a10g-large --timeout 3h --secrets HF_TOKEN \\
    scripts/ml/finetune/lora_job.py Qwen/Qwen3-4B-Instruct-2507 DATASET_REPO OUT_REPO
"""

import os
import sys

import torch
from datasets import load_dataset
from huggingface_hub import HfApi
from peft import LoraConfig
from transformers import AutoTokenizer
from trl import SFTConfig, SFTTrainer

MAX_LEN = 4096


def main(base: str, dataset_repo: str, out_repo: str) -> None:
    # a local .jsonl works too, that's how the smoke test runs it
    rows = (load_dataset("json", data_files=dataset_repo, split="train")
            if dataset_repo.endswith(".jsonl") else load_dataset(dataset_repo, split="train"))
    # prompt/completion: loss on the json answer only, not on the page text
    data = rows.map(lambda r: {"prompt": r["messages"][:1], "completion": r["messages"][1:]},
                    remove_columns=rows.column_names)
    # trl cuts over-long rows at the end = half a json answer as the target, drop them instead
    tok = AutoTokenizer.from_pretrained(base)
    fits = data.filter(lambda r: len(tok.apply_chat_template(
        r["prompt"] + r["completion"], tokenize=True)) <= MAX_LEN)
    print(f"{len(data) - len(fits)} rows over {MAX_LEN} tokens dropped")
    data = fits
    args = SFTConfig(
        output_dir="out", num_train_epochs=3, learning_rate=1e-4,
        per_device_train_batch_size=1, gradient_accumulation_steps=8,
        gradient_checkpointing=True, bf16=torch.cuda.is_available(),
        max_steps=int(os.environ.get("MAX_STEPS", -1)),
        max_length=MAX_LEN, logging_steps=5, save_strategy="no", report_to="none")
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear",
                      task_type="CAUSAL_LM")
    trainer = SFTTrainer(model=base, args=args, train_dataset=data, peft_config=lora)
    trainer.train()
    # merged bf16 weights, so awq_job and goethe see a plain model
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained("merged")
    AutoTokenizer.from_pretrained(base).save_pretrained("merged")
    if out_repo == "-":
        return  # smoke run, nothing to upload
    api = HfApi()
    api.create_repo(out_repo, private=True, exist_ok=True)
    api.upload_folder(folder_path="merged", repo_id=out_repo,
                      commit_message=f"lora sft of {base} on {dataset_repo}")
    print(f"uploaded {out_repo}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
