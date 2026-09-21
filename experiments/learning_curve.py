"""Learning curve — is the bottleneck data or model?

Trains the hybrid binary classifier and the multiclass relationship
classifier on 20/40/60/80/100% of train rows (5 seeds each), reports
test metrics against size. If the curve is still climbing at 100%, more
data helps; if flat, the problem is structural.

Usage:
    uv run python experiments/learning_curve.py
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, metrics  # noqa: E402
from experiments.hybrid import FEATURES, _X, _binary_report  # noqa: E402

ROWS = json.loads((common.RESULTS / "pair_features.json")
                  .read_text())["rows"]
FRACTIONS = [0.2, 0.4, 0.6, 0.8, 1.0]
SEEDS = [11, 23, 37, 51, 73]


def main() -> None:
    from sklearn.linear_model import LogisticRegression

    train = [r for r in ROWS
             if r["pair_split"] == "train" and r["pair_relationship"]]
    test = [r for r in ROWS
            if r["pair_split"] == "test" and r["pair_relationship"]]
    yte_bin = [1 if r["pair_relevance"] >= 1 else 0 for r in test]
    yte_mc = [r["pair_relationship"] for r in test]

    curve = defaultdict(list)
    for frac in FRACTIONS:
        for seed in SEEDS:
            rng = random.Random(seed)
            n = max(5, int(len(train) * frac))
            sample = rng.sample(train, n)
            yb = [1 if r["pair_relevance"] >= 1 else 0 for r in sample]
            ym = [r["pair_relationship"] for r in sample]
            X = [_X(r) for r in sample]

            if len(set(yb)) > 1:
                cb = LogisticRegression(max_iter=2000,
                                        class_weight="balanced")
                cb.fit(X, yb)
                curve[f"binary_f1@{frac}"].append(
                    _binary_report(
                        yte_bin,
                        list(cb.predict([_X(r) for r in test])))["f1"])
            if len(set(ym)) > 1:
                cm = LogisticRegression(max_iter=2000,
                                        class_weight="balanced")
                cm.fit(X, ym)
                curve[f"multiclass_f1@{frac}"].append(
                    metrics.classification_report(
                        yte_mc,
                        list(cm.predict([_X(r) for r in test])))["macro_f1"])

    out = {k: {"mean": round(sum(v) / len(v), 4),
               "runs": [round(x, 4) for x in v]}
           for k, v in sorted(curve.items())}
    common.save_result("learning_curve", {"curve": out, "n_train": len(train),
                                          "n_test": len(test)})
    for k, v in out.items():
        print(f"{k:20s} mean={v['mean']:.3f}  runs={v['runs']}")


if __name__ == "__main__":
    main()
