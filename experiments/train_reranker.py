"""Fine-tune a cross-encoder reranker on the train split, evaluate on test.

Pairs carry graded relevance (0/1/2); the cross-encoder trains it as a
regression target — standard practice for rerankers and honest for a tiny
dataset. The pretrained model is evaluated on the SAME test split so the
delta is a fair comparison, not a vibe.

Usage:
    uv run --group ml python experiments/train_reranker.py
    uv run --group ml python experiments/train_reranker.py --epochs 3 --batch 8
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402

BASE = "BAAI/bge-reranker-v2-m3"


def _evaluate(ce, coms, psgs, relevance) -> dict:
    ranked = {}
    for c in coms:
        pairs = [[f'{c["title"]} {c["text"]}', p["text"]] for p in psgs]
        scores = ce.predict(pairs)
        order = sorted(range(len(psgs)), key=lambda i: -scores[i])
        ranked[c["id"]] = [psgs[i]["id"] for i in order]
    return metrics.ranking_report(ranked, relevance)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--out", default="experiments/checkpoints/reranker_ft")
    args = ap.parse_args()
    common.seed_everything()

    coms = data.commitments()
    by_id = {c["id"]: c for c in coms}
    psgs = {p["id"]: p for p in data.passages()}
    rows = data.pairs()

    train_rows = [r for r in rows if r["split"] == "train"]
    test_psgs = [p for p in psgs.values() if data.split_of(p["source"]) == "test"]
    test_rel = {(l["commitment_id"], l["passage_id"]): l["relevance"]
                for l in data.labels()
                if data.split_of(l["passage_id"].split("#")[0]) == "test"}

    from sentence_transformers import CrossEncoder, InputExample
    from torch.utils.data import DataLoader

    examples = [
        InputExample(
            texts=[f'{by_id[r["commitment_id"]]["title"]} '
                   f'{by_id[r["commitment_id"]]["text"]}',
                   psgs[r["passage_id"]]["text"]],
            label=r["relevance"] / 2.0,
        )
        for r in train_rows
    ]
    print(f"train pairs: {len(examples)} "
          f"(pos={sum(1 for r in train_rows if r['relevance'] >= 1)})")

    ce = CrossEncoder(args.base, device=common.device(),
                      num_labels=1, max_length=512)

    with common.Timer() as t:
        before = _evaluate(ce, coms, test_psgs, test_rel)
        print(f"pretrained on test split: {before}")

        ce.fit(train_dataloader=DataLoader(examples, shuffle=True,
                                           batch_size=args.batch),
               epochs=args.epochs, warmup_steps=10, show_progress_bar=True)
        ce.save(args.out)

        after = _evaluate(ce, coms, test_psgs, test_rel)
        print(f"fine-tuned on test split: {after}")

    common.save_result("train_reranker", {
        "base": args.base, "epochs": args.epochs, "batch": args.batch,
        "train_pairs": len(examples), "checkpoint": args.out,
        "test_before": before, "test_after": after,
        "runtime_s": t.seconds,
    })


if __name__ == "__main__":
    main()
