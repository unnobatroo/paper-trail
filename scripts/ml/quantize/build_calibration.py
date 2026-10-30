"""hungarian calibration text for quantization, from the read-only cloud export

chunks are official jozsefvaros/rev8 pages and the climate strategy, so awq scales are fit
to the text the model will actually read. writes jsonl {"text": ...}, deterministic order

  uv run python scripts/ml/quantize/build_calibration.py EXPORT_DIR OUT.jsonl
"""

import hashlib
import json
import sys
from pathlib import Path

SAMPLES = 512
MIN_CHARS = 600


def main(export_dir: str, out: str) -> None:
    rows = [json.loads(line) for line in
            Path(export_dir, "chunks.jsonl").read_text().splitlines() if line]
    texts = {r["text"].strip() for r in rows if len(r["text"].strip()) >= MIN_CHARS}
    # stable spread across documents without a random seed to keep around
    ordered = sorted(texts, key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    with open(out, "w") as f:
        for text in ordered[:SAMPLES]:
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
    print(f"{min(SAMPLES, len(ordered))} of {len(ordered)} chunks -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
