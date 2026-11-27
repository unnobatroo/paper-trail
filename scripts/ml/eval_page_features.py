"""train the page prefilter and check it against the layout rule, one unseen town at a time

The labelled Hungarian pages come from 7 towns. A model is trained on 6 towns and scored on
the 7th, so the numbers say how it does on a plan it has never seen. Scores use only the
random samples; the stratified sample over-represents measure pages, so it is used for
training and for recall. Uncertain pages are dropped. The threshold is the highest one that
keeps leave-one-town-out recall at or above --recall on the random pages.

  uv run --with scikit-learn python scripts/ml/eval_page_features.py [--export FILE]
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
from layout_rule import FIELDS, field_count
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from paper_trail.ml.prefilter import PagePrefilter

SILVER = Path("data/eval_ext/silver")
RANDOM = [("sample_hu4", "labels_hu4"), ("sample_hu3_heldout", "labels_hu3_heldout"),
          ("sample_more", "labels_more")]
STRAT = [("sample_strat", "labels_strat")]

COUNTS = {
    "deadline": r"Határid|Időtáv|Ütemezés",
    "owner": r"Felelős",
    "cost": r"Finanszírozási\s+igény|Összköltség|(?:millió|M|Mrd)\s*Ft",
    "code": r"\b(?:M|A|Aá|Sz|SZ|Dá)\s?-?\(?\d{1,2}(?:\.\d)?\)?\b",
    "measure": r"intézkedés|beavatkozás",
    "figure": r"\d+\. ábra|Forrás:",
    "goal": r"célkitűzés",
    "indicator": r"indikátor|Mérték-?\s*egység",
}
SPEC = {"fields": FIELDS, "counts": COUNTS}
BLANK = {**SPEC, "name": "blank", "threshold": 0.5, "intercept": 0.0,
         "mean": [0.0] * (len(COUNTS) + 3), "scale": [1.0] * (len(COUNTS) + 3),
         "coef": [0.0] * (len(COUNTS) + 3)}


def load(samples: list[tuple[str, str]]) -> list[dict]:
    rows = []
    for sample_file, label_file in samples:
        sample = json.loads((SILVER / f"{sample_file}.json").read_text(encoding="utf-8"))
        labels = json.loads((SILVER / f"{label_file}.json").read_text(encoding="utf-8"))
        for doc, lab in labels.items():
            if not isinstance(lab, dict) or "positive" not in lab:
                continue
            for value, key in ((1, "positive"), (0, "negative")):
                rows += [{"doc": doc, "label": value, "text": sample[doc][str(page)]}
                         for page in lab[key]]
    return rows


def prf(gold: np.ndarray, pred: np.ndarray) -> dict:
    tp, fp, fn = int((gold & pred).sum()), int((~gold & pred).sum()), int((gold & ~pred).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def fit(x: np.ndarray, y: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler().fit(x)
    clf = LogisticRegression(class_weight="balanced", C=0.3, max_iter=2000)
    return scaler, clf.fit(scaler.transform(x), y)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", type=Path, help="write the model file trained on every page")
    ap.add_argument("--recall", type=float, default=0.85)
    args = ap.parse_args()
    warnings.filterwarnings("ignore")

    featurize = PagePrefilter(BLANK).features
    rand, strat = load(RANDOM), load(STRAT)
    x_r, x_s = (np.array([featurize(r["text"]) for r in rows]) for rows in (rand, strat))
    y_r, y_s = (np.array([r["label"] for r in rows], bool) for rows in (rand, strat))
    t_r, t_s = (np.array([r["doc"] for r in rows]) for rows in (rand, strat))
    towns = sorted({str(t) for t in t_r})
    print(f"random pages {len(rand)} ({y_r.sum()} positive), stratified {len(strat)} "
          f"({y_s.sum()} positive), towns {towns}")

    score_r, score_s = np.zeros(len(rand)), np.zeros(len(strat))
    for town in towns:
        scaler, clf = fit(np.vstack([x_r[t_r != town], x_s[t_s != town]]),
                          np.concatenate([y_r[t_r != town], y_s[t_s != town]]))
        score_r[t_r == town] = clf.predict_proba(scaler.transform(x_r[t_r == town]))[:, 1]
        score_s[t_s == town] = clf.predict_proba(scaler.transform(x_s[t_s == town]))[:, 1]

    rule_r = np.array([field_count(r["text"]) >= 2 for r in rand])
    print("random pages, leave-one-town-out")
    print("  layout rule ", prf(y_r, rule_r))
    print("  threshold   precision recall  f1   pages kept")
    chosen = 0.0  # keep every page if no threshold reaches the recall target
    for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        m = prf(y_r, score_r >= t)
        kept = float((score_r >= t).mean())
        print(f"  {t:.1f}         {m['precision']:.3f}     {m['recall']:.3f}   {m['f1']:.3f} "
              f"{kept:.0%}")
    for t in np.arange(0.05, 0.96, 0.05):
        if prf(y_r, score_r >= t)["recall"] >= args.recall:
            chosen = round(float(t), 2)
    if chosen == 0.0:
        print(f"no threshold reaches recall {args.recall}; the prefilter would keep every page")
    print(f"threshold for recall >= {args.recall}: {chosen}")
    pred = score_r >= chosen
    rng = np.random.default_rng(13)
    diffs = []
    for _ in range(2000):
        i = rng.integers(0, len(y_r), len(y_r))
        diffs.append(prf(y_r[i], pred[i])["f1"] - prf(y_r[i], rule_r[i])["f1"])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"  at {chosen}: {prf(y_r, pred)}")
    print(f"  F1 minus layout rule: {np.mean(diffs):+.3f} (95% {lo:+.3f} to {hi:+.3f})")
    print("  recall by town:", {t: prf(y_r[t_r == t], pred[t_r == t])["recall"] for t in towns})
    print("stratified pages (recall only)")
    print("  layout rule ", prf(y_s, np.array([field_count(r["text"]) >= 2 for r in strat])))
    print(f"  at {chosen}:", prf(y_s, score_s >= chosen))

    if args.export:
        scaler, clf = fit(np.vstack([x_r, x_s]), np.concatenate([y_r, y_s]))
        spec = {**SPEC, "name": "pf1", "threshold": chosen,
                "intercept": float(clf.intercept_[0]), "coef": clf.coef_[0].tolist(),
                "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                "trained_on": f"{len(rand)} random + {len(strat)} stratified Hungarian pages",
                "leave_one_town_out": prf(y_r, pred)}
        args.export.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
        print("wrote", args.export)


if __name__ == "__main__":
    main()
