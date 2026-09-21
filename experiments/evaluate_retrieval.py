"""Baseline: how well does each embedding model rank evidence passages?

Scores every (commitment × passage) pair by cosine similarity, ranks the
corpus per commitment, and reports Recall@k / Precision@k / MRR / nDCG@10
against the curated labels.

Usage:
    uv run --group ml python experiments/evaluate_retrieval.py
    uv run --group ml python experiments/evaluate_retrieval.py \
        --models sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2,BAAI/bge-m3
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402

DEFAULT_MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # current
    "BAAI/bge-m3",
    "intfloat/multilingual-e5-large-instruct",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    coms = data.commitments()
    psgs = data.passages()
    relevance = {(l["commitment_id"], l["passage_id"]): l["relevance"]
                 for l in data.labels()}
    queries = {c["id"]: f'{c["title"]} {c["text"]}' for c in coms}
    corpus = [p["text"] for p in psgs]
    pids = [p["id"] for p in psgs]

    from sentence_transformers import SentenceTransformer
    import numpy as np

    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        with common.Timer() as t:
            model = SentenceTransformer(name, device=common.device())
            qv = model.encode(list(queries.values()),
                              batch_size=args.batch, normalize_embeddings=True)
            pv = model.encode(corpus, batch_size=args.batch,
                              normalize_embeddings=True)
            sims = np.asarray(qv) @ np.asarray(pv).T  # (n_q, n_p)

            ranked = {}
            for qi, cid in enumerate(queries):
                order = np.argsort(-sims[qi])
                ranked[cid] = [pids[j] for j in order]

            rep = metrics.ranking_report(ranked, relevance)
            rep["runtime_s"] = t.seconds
        common.save_result("retrieval", {"model": name, "metrics": rep,
                                         "n_passages": len(psgs),
                                         "n_queries": len(coms)})
        print(f"{name}\n  {rep}")


if __name__ == "__main__":
    main()
