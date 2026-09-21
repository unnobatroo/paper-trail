"""Train a lightweight relationship classifier.

Predicts the app's RelationshipType for (commitment, passage) pairs.
Two feature modes:

    --features tfidf    word n-grams over "title + text || passage" + LogReg
    --features embed    [q, p, |q-p|, q*p] sentence embeddings + LogReg

Trains on the train split, reports val + test metrics, saves joblib.

Usage:
    uv run --group ml python experiments/train_classifier.py --features tfidf
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402

OUT = "experiments/checkpoints/classifier.joblib"


def _features(mode: str, rows, coms, psgs, model=None):
    import numpy as np
    texts = [
        f'{coms[r["commitment_id"]]["title"]} '
        f'{coms[r["commitment_id"]]["text"]} || '
        f'{psgs[r["passage_id"]]["text"]}'
        for r in rows
    ]
    if mode == "tfidf":
        return texts  # vectorizer handles it
    q = model.encode(
        [f'{coms[r["commitment_id"]]["title"]} {coms[r["commitment_id"]]["text"]}'
         for r in rows], normalize_embeddings=True)
    p = model.encode([psgs[r["passage_id"]]["text"] for r in rows],
                     normalize_embeddings=True)
    return np.concatenate([q, p, np.abs(q - p), q * p], axis=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", choices=["tfidf", "embed"], default="tfidf")
    ap.add_argument("--embed_model",
                    default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    common.seed_everything()

    coms = {c["id"]: c for c in data.commitments()}
    psgs = {p["id"]: p for p in data.passages()}
    rows = [r for r in data.pairs() if r["relationship"]]
    train = [r for r in rows if r["split"] == "train"]
    val = [r for r in rows if r["split"] == "val"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"pairs train={len(train)} val={len(val)} test={len(test)}")

    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    import joblib

    st_model = None
    if args.features == "embed":
        from sentence_transformers import SentenceTransformer
        st_model = SentenceTransformer(args.embed_model, device=common.device())

    X_train = _features(args.features, train, coms, psgs, st_model)
    y_train = [r["relationship"] for r in train]

    with common.Timer() as t:
        if args.features == "tfidf":
            clf = Pipeline([
                ("vec", TfidfVectorizer(ngram_range=(1, 2), min_df=1,
                                        sublinear_tf=True)),
                ("lr", LogisticRegression(max_iter=2000,
                                          class_weight="balanced")),
            ])
        else:
            clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        clf.fit(X_train, y_train)

        reports = {}
        for split_name, split_rows in (("val", val), ("test", test)):
            Xs = _features(args.features, split_rows, coms, psgs, st_model)
            ys = [r["relationship"] for r in split_rows]
            rep = metrics.classification_report(ys, list(clf.predict(Xs)))
            reports[split_name] = rep
            print(f"{split_name}: acc={rep['accuracy']} macroF1={rep['macro_f1']}")
        common.save_result("train_classifier", {
            "features": args.features,
            "n_train": len(train), "metrics": reports,
            "runtime_s": t.seconds,
        })

    import pathlib
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"features": args.features, "embed_model": args.embed_model,
                 "clf": clf}, args.out)
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
