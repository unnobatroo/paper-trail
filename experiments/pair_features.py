"""Compute the feature vector for every (commitment, passage) combo, once.

Writes experiments/results/pair_features.json — downstream scripts
(hybrid, learning curve, error analysis, ablation) read it instead of
re-embedding / re-scoring. Keeps GPU work in one place.

One row per commitment × passage (8 × 91 = 728):
    sim            MiniLM cosine (production embedder)
    ce_pretrained  bge-reranker-v2-m3 score
    ce_finetuned   fine-tuned checkpoint score (if it exists)
    n_orgs / n_places / n_dates   shared-entity counts
    has_budget     money figure found in passage
    heuristic_score / heuristic_rel   production matching output
    label_relevance / label_relationship   curated label, or null
    pair_*         derived training row from data.pairs(), or null

Usage:
    uv run --group ml python experiments/pair_features.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from experiments import common, data  # noqa: E402

from paper_trail.domain.enums import CandidateType  # noqa: E402
from paper_trail.domain.models import Commitment, EvidenceItem  # noqa: E402
from paper_trail.ml import entities, matching  # noqa: E402

OUT = common.RESULTS / "pair_features.json"
EMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CE_BASE = "BAAI/bge-reranker-v2-m3"
CE_FT = "experiments/checkpoints/reranker_ft"


def main() -> None:
    coms = {c["id"]: c for c in data.commitments()}
    psgs = {p["id"]: p for p in data.passages()}
    pids = list(psgs)

    label_map = {(l["commitment_id"], l["passage_id"]): l
                 for l in data.labels()}
    pair_map = {(r["commitment_id"], r["passage_id"]): r
                for r in data.pairs()}

    from sentence_transformers import SentenceTransformer, CrossEncoder

    st = SentenceTransformer(EMBED, device=common.device())
    qv = {cid: st.encode([f'{c["title"]} {c["text"]}'],
                       normalize_embeddings=True)[0]
          for cid, c in coms.items()}
    pv = {pid: st.encode([p["text"]], normalize_embeddings=True)[0]
          for pid, p in psgs.items()}

    ce_base = CrossEncoder(CE_BASE, device=common.device())
    ce_ft = (CrossEncoder(CE_FT, device=common.device())
             if pathlib.Path(CE_FT).exists() else None)

    ce_scores = {}
    for cid, c in coms.items():
        pairs = [[f'{c["title"]} {c["text"]}', psgs[pid]["text"]]
                 for pid in pids]
        ce_scores[cid] = {
            "base": [float(s) for s in ce_base.predict(pairs)],
            "ft": ([float(s) for s in ce_ft.predict(pairs)]
                   if ce_ft else None),
        }

    out = []
    for cid, c in coms.items():
        com = Commitment(kind=CandidateType.MEASURE, title=c["title"],
                         summary=c["text"], code=c["code"])
        for i, pid in enumerate(pids):
            p = psgs[pid]
            sim = float(qv[cid] @ pv[pid])
            ev = EvidenceItem(
                commitment_id=0, url=p["url"], title=pid,
                organisations=entities.extract_organisations(p["text"]),
                locations=entities.extract_locations(p["text"]),
                dates_mentioned=entities.extract_dates(p["text"]),
            )
            feats = matching.compute_features(com, ev, sim)
            has_budget = any(m.kind for m in entities.extract_money(p["text"]))
            rel, _ = matching.suggest_relationship(feats, has_budget)
            lab = label_map.get((cid, pid))
            pr = pair_map.get((cid, pid))
            out.append({
                "commitment_id": cid, "passage_id": pid,
                "source": p["source"], "split": data.split_of(p["source"]),
                "sim": round(sim, 4),
                "ce_pretrained": round(ce_scores[cid]["base"][i], 4),
                "ce_finetuned": (round(ce_scores[cid]["ft"][i], 4)
                                 if ce_ft else None),
                "n_orgs": len(feats.shared_organisations),
                "n_places": len(feats.shared_locations),
                "n_dates": len(feats.shared_dates),
                "has_budget": has_budget,
                "heuristic_score": matching.score(feats),
                "heuristic_rel": rel.value,
                "label_relevance": lab["relevance"] if lab else None,
                "label_relationship": lab["relationship"] if lab else None,
                "pair_relevance": pr["relevance"] if pr else None,
                "pair_relationship": pr["relationship"] if pr else None,
                "pair_split": pr["split"] if pr else None,
            })

    OUT.write_text(json.dumps({"embed_model": EMBED, "ce_base": CE_BASE,
                               "ce_finetuned": CE_FT if ce_ft else None,
                               "rows": out}, ensure_ascii=False, indent=1))
    print(f"wrote {len(out)} rows -> {OUT}")


if __name__ == "__main__":
    main()
