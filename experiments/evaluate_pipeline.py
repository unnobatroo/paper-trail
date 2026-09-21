"""Retrieve-then-rerank — the pipeline shape the app actually uses.

Stage 1: MiniLM retrieves top-K passages per commitment.
Stage 2: a cross-encoder reranks those K only.

Reports retrieval recall@5 (how much evidence stage 1 keeps in play) and
final ranking quality for: no reranker, pretrained CE, fine-tuned CE.
This is the honest 'does the reranker help the real pipeline' number —
not full-corpus reranking, which the app never does.

Usage:
    uv run --group ml python experiments/evaluate_pipeline.py
    uv run --group ml python experiments/evaluate_pipeline.py --k 10
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402

EMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CE_BASE = "BAAI/bge-reranker-v2-m3"
CE_FT = "experiments/checkpoints/reranker_ft"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--embed", default=EMBED)
    args = ap.parse_args()

    coms = data.commitments()
    psgs = data.passages()
    pids = [p["id"] for p in psgs]
    relevance = {(l["commitment_id"], l["passage_id"]): l["relevance"]
                 for l in data.labels()}

    import pathlib
    from sentence_transformers import SentenceTransformer, CrossEncoder
    import numpy as np

    st = SentenceTransformer(args.embed, device=common.device())
    qv = st.encode([f'{c["title"]} {c["text"]}' for c in coms],
                   normalize_embeddings=True)
    pv = st.encode([p["text"] for p in psgs], normalize_embeddings=True)
    sims = np.asarray(qv) @ np.asarray(pv).T

    topk: dict[str, list[int]] = {}
    for qi, c in enumerate(coms):
        topk[c["id"]] = list(np.argsort(-sims[qi])[: args.k])

    # stage-1 quality: what fraction of gold survives to stage 2
    stage1 = {}
    for c in coms:
        gold = {p for (cid, p), r in relevance.items()
                if cid == c["id"] and r >= 1}
        kept = gold & {pids[i] for i in topk[c["id"]]}
        stage1[c["id"]] = {"gold": len(gold), "in_topk": len(kept)}
    n_gold = sum(v["gold"] for v in stage1.values())
    n_kept = sum(v["in_topk"] for v in stage1.values())
    print(f"stage1 top-{args.k}: keeps {n_kept}/{n_gold} gold passages "
          f"({n_kept / n_gold:.2f} recall ceiling)")

    rankers = {"none": None, "ce_pretrained": CE_BASE}
    if pathlib.Path(CE_FT).exists():
        rankers["ce_finetuned"] = CE_FT
    results = {"stage1": stage1, "k": args.k}

    for name, model_path in rankers.items():
        ce = (CrossEncoder(model_path, device=common.device())
              if model_path else None)
        ranked = {}
        for qi, c in enumerate(coms):
            idxs = topk[c["id"]]
            if ce:
                scores = ce.predict(
                    [[f'{c["title"]} {c["text"]}', psgs[i]["text"]]
                     for i in idxs])
                order = sorted(range(len(idxs)), key=lambda i: -scores[i])
                ranked[c["id"]] = [pids[idxs[i]] for i in order]
            else:
                ranked[c["id"]] = [pids[i] for i in idxs]
        results[name] = metrics.ranking_report(ranked, relevance)
        print(f"{name:14s} {results[name]}")

    common.save_result("pipeline", {"embed": args.embed, "results": results})


if __name__ == "__main__":
    main()
