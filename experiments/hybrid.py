"""Hybrid classifier — is ML more useful as an extra signal than a replacement?

Logistic regression over *meaningful* features only:

    sim, ce_pretrained, ce_finetuned,
    n_orgs, n_places, n_dates, has_budget, heuristic_score

Two honest tasks:
    binary      is this passage evidence for the commitment? (relevance >= 1)
    multiclass  which relationship? (the 5-class problem we know is thin)

Compared on the SAME test rows against: heuristic alone, sim alone,
ce_pretrained alone. Train on pair rows only.

Usage:
    uv run python experiments/hybrid.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from experiments import common, metrics  # noqa: E402

ROWS = json.loads((common.RESULTS / "pair_features.json")
                  .read_text())["rows"]

FEATURES = ["sim", "ce_pretrained", "ce_finetuned",
            "n_orgs", "n_places", "n_dates", "has_budget",
            "heuristic_score"]


def _X(row: dict) -> list[float]:
    return [float(row[f] or 0) for f in FEATURES]


def _binary_report(y_true, y_pred) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    return {"accuracy": round(acc, 4), "precision": round(prec, 3),
            "recall": round(rec, 3), "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn}


def main() -> None:
    from sklearn.linear_model import LogisticRegression

    train = [r for r in ROWS
             if r["pair_split"] == "train" and r["pair_relationship"]]
    test = [r for r in ROWS
            if r["pair_split"] == "test" and r["pair_relationship"]]
    print(f"train={len(train)} test={len(test)}")

    # ---- binary: evidence vs not --------------------------------------------
    ytr_bin = [1 if r["pair_relevance"] >= 1 else 0 for r in train]
    yte_bin = [1 if r["pair_relevance"] >= 1 else 0 for r in test]
    print("binary train balance:", dict(Counter(ytr_bin)),
          "| test:", dict(Counter(yte_bin)))

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit([_X(r) for r in train], ytr_bin)
    hybrid = list(clf.predict([_X(r) for r in test]))

    sims = [r["sim"] for r in ROWS if r["pair_relevance"] is not None]
    labels_bin = [1 if r["pair_relevance"] >= 1 else 0
                  for r in ROWS if r["pair_relevance"] is not None]
    # pick the sim threshold that best separates on train rows only
    tr_sims = [r["sim"] for r in train]
    thr = max(tr_sims, key=lambda t: sum(
        (s >= t) == (y == 1) for s, y in zip(tr_sims, ytr_bin)))

    baseline = {
        "heuristic_pos": [1 if r["heuristic_rel"] != "probably_unrelated" else 0
                          for r in test],
        "sim_threshold": [1 if r["sim"] >= thr else 0 for r in test],
        "ce_pretrained": [1 if r["ce_pretrained"] > 0 else 0 for r in test],
        "ce_finetuned": [1 if (r["ce_finetuned"] or -9) > 0 else 0
                         for r in test],
        "hybrid_lr": hybrid,
    }
    out = {"binary": {
        n: _binary_report(yte_bin, p) for n, p in baseline.items()}}

    # ---- multiclass: relationship --------------------------------------------
    ytr_mc = [r["pair_relationship"] for r in train]
    yte_mc = [r["pair_relationship"] for r in test]
    clf_mc = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf_mc.fit([_X(r) for r in train], ytr_mc)
    out["multiclass"] = {
        "hybrid_lr": metrics.classification_report(
            yte_mc, list(clf_mc.predict([_X(r) for r in test]))),
        "heuristic": metrics.classification_report(
            yte_mc, [r["heuristic_rel"] for r in test]),
    }

    coef = dict(zip(FEATURES, [round(c, 3) for c in clf.coef_[0]]))
    out["binary_coef"] = coef
    common.save_result("hybrid", out)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
