"""Evaluate a cross-encoder reranker on the benchmark.

Scores (commitment, passage) pairs with a pretrained or fine-tuned
cross-encoder, ranks the corpus per commitment, reports the same metrics as
the retrieval baseline — so the comparison is direct.

Usage:
    uv run --group ml python experiments/evaluate_reranker.py
    uv run --group ml python experiments/evaluate_reranker.py \
        --checkpoint experiments/checkpoints/reranker_ft --split test
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--checkpoint", default=None,
                    help="fine-tuned checkpoint dir (overrides --model)")
    ap.add_argument("--split", default="all", choices=["all", "train", "val", "test"],
                    help="restrict passages to one split")
    args = ap.parse_args()

    coms = data.commitments()
    psgs = [p for p in data.passages()
            if args.split == "all" or data.split_of(p["source"]) == args.split]
    relevance = {(l["commitment_id"], l["passage_id"]): l["relevance"]
                 for l in data.labels()
                 if args.split == "all"
                 or data.split_of(l["passage_id"].split("#")[0]) == args.split}

    from sentence_transformers import CrossEncoder

    name = args.checkpoint or args.model
    with common.Timer() as t:
        ce = CrossEncoder(name, device=common.device())
        ranked = {}
        for c in coms:
            pairs = [[f'{c["title"]} {c["text"]}', p["text"]] for p in psgs]
            scores = ce.predict(pairs)
            order = sorted(range(len(psgs)), key=lambda i: -scores[i])
            ranked[c["id"]] = [psgs[i]["id"] for i in order]
        rep = metrics.ranking_report(ranked, relevance)
        rep["runtime_s"] = t.seconds

    common.save_result("reranker", {"model": name, "split": args.split,
                                    "metrics": rep,
                                    "n_passages": len(psgs)})
    print(f"{name} [{args.split}]\n  {rep}")


if __name__ == "__main__":
    main()
