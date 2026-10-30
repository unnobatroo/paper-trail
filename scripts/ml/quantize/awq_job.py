# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "llmcompressor==0.14.0",
#   "compressed-tensors==0.19.0",
#   "transformers==5.17.0",
#   "torch==2.14.0",
#   "accelerate==1.15.0",
#   "datasets==5.0.1",
#   "huggingface_hub>=1.0",
# ]
# ///
"""4-bit awq of a base model, calibrated on our hungarian municipal text

runs as an hf job (needs HF_TOKEN), uploads to a PRIVATE repo. going public is a
separate call, after it wins the eval

  hf jobs uv run --flavor a10g-large --timeout 2h --secrets HF_TOKEN \\
    scripts/ml/quantize/awq_job.py BASE CALIBRATION_DATASET OUT_REPO
"""

import sys

from datasets import load_dataset
from huggingface_hub import HfApi
from llmcompressor import oneshot
from llmcompressor.modifiers.awq import AWQModifier
from transformers import AutoModelForCausalLM, AutoTokenizer

# awq caches activations per sample: 512 x 1024 ran out of memory on a 24 gb a10g
MAX_LEN = 512
SAMPLES = 256


def main(base: str, calibration: str, out_repo: str) -> None:
    tokenizer = AutoTokenizer.from_pretrained(base)
    model = AutoModelForCausalLM.from_pretrained(base, dtype="auto")
    texts = load_dataset(calibration, split="train").select(range(SAMPLES))
    data = texts.map(lambda r: tokenizer(r["text"], truncation=True, max_length=MAX_LEN),
                     remove_columns=texts.column_names)
    # lm_head stays bf16, asymmetric w4 with group 128 is what sglang's awq marlin kernels expect
    recipe = [AWQModifier(ignore=["lm_head"], scheme="W4A16_ASYM", targets=["Linear"])]
    oneshot(model=model, dataset=data, recipe=recipe, max_seq_length=MAX_LEN,
            num_calibration_samples=len(data))
    out = "quantized"
    model.save_pretrained(out, save_compressed=True)
    tokenizer.save_pretrained(out)
    api = HfApi()
    api.create_repo(out_repo, private=True, exist_ok=True)
    message = f"awq w4a16 of {base}, {len(data)} hungarian calibration samples"
    api.upload_folder(folder_path=out, repo_id=out_repo, commit_message=message)
    print("uploaded", out_repo)


if __name__ == "__main__":
    main(*sys.argv[1:4])
