"""Evaluate relationship classification on the test split.

Compares two predictors on identical rows:
  * heuristic — the app's current weighted-score + threshold rules
    (matching.suggest_relationship with real features + MiniLM similarity)
  * trained   — a joblib checkpoint from train_classifier.py

Usage:
    uv run --group ml python experiments/evaluate_classifier.py
    uv run --group ml python experiments/evaluate_classifier.py \
        --checkpoint experiments/checkpoints/classifier.joblib
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from experiments import common, data, metrics  # noqa: E402
from experiments.train_classifier import _features  # noqa: E402

from paper_trail.domain.enums import CandidateType  # noqa: E402
from paper_trail.domain.models import Commitment, EvidenceItem  # noqa: E402
from paper_trail.ml import entities, matching  # noqa: E402

DEFAULT_EMBED = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _heuristic(com: Commitment, ev: EvidenceItem, sim: float, has_budget: bool):
    feats = matching.compute_features(com, ev, sim)
    rel, _ = matching.suggest_relationship(feats, has_budget)
    return rel.value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="experiments/checkpoints/classifier.joblib")
    ap.add_argument("--embed_model", default=DEFAULT_EMBED)
    args = ap.parse_args()

    coms = {c["id"]: c for c in data.commitments()}
    psgs = {p["id"]: p for p in data.passages()}
    test = [r for r in data.pairs()
            if r["relationship"] and r["split"] == "test"]
    print(f"test pairs: {len(test)}")
    y_true = [r["relationship"] for r in test]

    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(args.embed_model, device=common.device())

    # -- heuristic baseline ---------------------------------------------------
    with common.Timer() as t:
        preds = []
        for r in test:
            c = coms[r["commitment_id"]]
            p = psgs[r["passage_id"]]
            com = Commitment(kind=CandidateType.MEASURE, title=c["title"],
                             summary=c["text"], code=c["code"])
            ev = EvidenceItem(
                commitment_id=0, url=p["url"], title=p["id"],
                organisations=entities.extract_organisations(p["text"]),
                locations=entities.extract_locations(p["text"]),
                dates_mentioned=entities.extract_dates(p["text"]),
            )
            qv = st.encode([f'{c["title"]} {c["text"]}'],
                           normalize_embeddings=True)[0]
            pv = st.encode([p["text"]], normalize_embeddings=True)[0]
            sim = float(qv @ pv)
            has_budget = any(m.kind for m in entities.extract_money(p["text"]))
            preds.append(_heuristic(com, ev, sim, has_budget))
        rep = metrics.classification_report(y_true, preds)
        print(f"heuristic: acc={rep['accuracy']} macroF1={rep['macro_f1']}")
        common.save_result("classifier", {"model": "heuristic",
                                          "split": "test", "metrics": rep,
                                          "runtime_s": t.seconds})

    # -- trained model ---------------------------------------------------------
    import pathlib
    if pathlib.Path(args.checkpoint).exists():
        import joblib
        bundle = joblib.load(args.checkpoint)
        st2 = None
        if bundle["features"] == "embed":
            st2 = SentenceTransformer(bundle["embed_model"],
                                      device=common.device())
        X = _features(bundle["features"], test, coms, psgs, st2)
        rep = metrics.classification_report(
            y_true, list(bundle["clf"].predict(X)))
        print(f"trained({bundle['features']}): acc={rep['accuracy']} "
              f"macroF1={rep['macro_f1']}")
        common.save_result("classifier", {
            "model": f"trained-{bundle['features']}", "split": "test",
            "metrics": rep,
        })
    else:
        print(f"no checkpoint at {args.checkpoint} — "
              "run train_classifier.py first")


if __name__ == "__main__":
    main()
