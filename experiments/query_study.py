"""Query-construction study — what should the stage-1 query be?

Variants per commitment:
    title          just the measure name
    text           the full commitment text only
    title_text     current production choice
    full           title + text + deterministic entities (orgs/places/dates
                   extracted from the commitment itself)

Run on a frozen corpus (default fixed_2400) with each model.

Usage:
    uv run --group ml python experiments/query_study.py
    uv run --group ml python experiments/query_study.py --corpus fixed_1200
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from experiments import common, corpus, data, metrics  # noqa: E402
from paper_trail.domain.enums import CandidateType  # noqa: E402
from paper_trail.domain.models import Commitment  # noqa: E402
from paper_trail.ml import matching  # noqa: E402

MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-large-instruct",
]


def _queries(coms, variant: str) -> list[str]:
    out = []
    for c in coms:
        if variant == "title":
            out.append(c["title"])
        elif variant == "text":
            out.append(c["text"])
        elif variant == "title_text":
            out.append(f'{c["title"]} {c["text"]}')
        elif variant == "full":
            com = Commitment(kind=CandidateType.MEASURE, title=c["title"],
                             summary=c["text"], code=c["code"])
            ent = matching.commitment_entities(com)
            extras = " ".join(sorted(ent["orgs"] | ent["locations"]
                                     | ent["dates"]))
            out.append(f'{c["title"]} {c["text"]} {extras}'.strip())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="fixed_2400")
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args()

    chunks, relevance = corpus.load(args.corpus)
    coms = data.commitments()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]

    from sentence_transformers import SentenceTransformer
    import numpy as np

    report = {}
    for mname in [m.strip() for m in args.models.split(",") if m.strip()]:
        model = SentenceTransformer(mname, device=common.device())
        pv = model.encode(texts, normalize_embeddings=True)
        for variant in ("title", "text", "title_text", "full"):
            qs = _queries(coms, variant)
            qv = model.encode(qs, normalize_embeddings=True)
            sims = np.asarray(qv) @ np.asarray(pv).T
            ranked = {}
            for qi, c in enumerate(coms):
                order = np.argsort(-sims[qi])
                ranked[c["id"]] = [ids[j] for j in order]
            rep = metrics.ranking_report(ranked, relevance,
                                       k_list=(5, 10, 20))
            key = f"{mname.split('/')[-1]} | {variant}"
            report[key] = rep
            print(f"{key:52s} r@5={rep['recall@5']:.3f} "
                  f"r@10={rep['recall@10']:.3f} "
                  f"r@20={rep['recall@20']:.3f} "
                  f"ndcg={rep['ndcg@10']:.3f} mrr={rep['mrr']:.3f}")

    common.save_result("query_study",
                       {"corpus": args.corpus, "results": report})


if __name__ == "__main__":
    main()
