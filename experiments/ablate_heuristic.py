"""Heuristic ablation — what information does the production score carry?

Ranks the full corpus per commitment using score variants and reports
ranking metrics for each. Answers: which components matter, and is the
weighted score better than cosine alone?

Variants:
    full           production score (0.6 sim + orgs + places + dates)
    sim_only       cosine alone
    entities_only  entity overlap without cosine
    no_orgs / no_places / no_dates   leave-one-out
    ce_pretrained / ce_finetuned   cross-encoder rankings for comparison

Usage:
    uv run python experiments/ablate_heuristic.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402
from paper_trail.ml.matching import (  # noqa: E402
    W_DATE, W_LOCATION, W_ORG, W_SIMILARITY,
)

ROWS = json.loads((common.RESULTS / "pair_features.json")
                  .read_text())["rows"]


def _score(r: dict, w_sim=W_SIMILARITY, w_org=W_ORG,
           w_place=W_LOCATION, w_date=W_DATE) -> float:
    return (w_sim * r["sim"]
            + w_org * min(r["n_orgs"], 2) / 2
            + w_place * min(r["n_places"], 2) / 2
            + w_date * min(r["n_dates"], 2) / 2)


VARIANTS = {
    "full": lambda r: _score(r),
    "sim_only": lambda r: r["sim"],
    "entities_only": lambda r: _score(r, w_sim=0, w_org=1 / 3,
                                      w_place=1 / 3, w_date=1 / 3),
    "no_orgs": lambda r: _score(r, w_org=0, w_sim=0.75),
    "no_places": lambda r: _score(r, w_place=0, w_sim=0.75),
    "no_dates": lambda r: _score(r, w_date=0, w_sim=0.70),
    "ce_pretrained": lambda r: r["ce_pretrained"],
    "ce_finetuned": lambda r: (r["ce_finetuned"]
                               if r["ce_finetuned"] is not None else -9),
}


def main() -> None:
    relevance = {(l["commitment_id"], l["passage_id"]): l["relevance"]
                 for l in data.labels()}
    results = {}
    for name, fn in VARIANTS.items():
        ranked = defaultdict(list)
        for r in sorted(ROWS, key=lambda r: -fn(r)):
            ranked[r["commitment_id"]].append(r["passage_id"])
        results[name] = metrics.ranking_report(dict(ranked), relevance)

    common.save_result("ablate_heuristic", {"results": results})
    for name, rep in results.items():
        print(f"{name:15s} r@5={rep['recall@5']:.3f} "
              f"p@5={rep['precision@5']:.3f} mrr={rep['mrr']:.3f} "
              f"ndcg={rep['ndcg@10']:.3f}")


if __name__ == "__main__":
    main()
