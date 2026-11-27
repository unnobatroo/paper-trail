"""what the prefilter costs end to end: extractor alone vs prefilter + extractor, page level

Takes the extractor's per-page flags (eval_silver_pages.py reports, "flagged") on the
labelled Hungarian pages and the prefilter's leave-one-town-out scores for the same pages, so
no page is scored by a prefilter that trained on it. A page counts as found when the
prefilter keeps it AND the extractor flags it. Józsefváros has no PDF here and no
prefilter score, so it is left out. Only the random samples give honest precision.

  uv run --with scikit-learn python scripts/ml/eval_combined.py report1.json:sample1:labels1 ...
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
from eval_page_features import BLANK, RANDOM, STRAT, fit, load, prf

from paper_trail.ml.prefilter import PagePrefilter

SILVER = Path("data/eval_ext/silver")


def main() -> None:
    warnings.filterwarnings("ignore")
    flags = {}
    for arg in sys.argv[1:]:
        report = json.loads(Path(arg).read_text(encoding="utf-8"))
        for doc, d in report["per_doc"].items():
            flags.setdefault(doc, set()).update(d["flagged"])
    featurize = PagePrefilter(BLANK).features
    rand, strat = load(RANDOM), load(STRAT)
    rows = rand + strat
    kind = np.array(["random"] * len(rand) + ["strat"] * len(strat))
    x = np.array([featurize(r["text"]) for r in rows])
    y = np.array([r["label"] for r in rows], bool)
    town = np.array([r["doc"] for r in rows])
    pages = []
    for _, label_file in RANDOM + STRAT:
        labels = json.loads((SILVER / f"{label_file}.json").read_text(encoding="utf-8"))
        for doc, lab in labels.items():
            if isinstance(lab, dict) and "positive" in lab:
                pages += [(doc, p) for key in ("positive", "negative") for p in lab[key]]
    assert len(pages) == len(rows)
    score = np.zeros(len(rows))
    for t in sorted(set(town)):
        test = town == t
        scaler, clf = fit(x[~test], y[~test])
        score[test] = clf.predict_proba(scaler.transform(x[test]))[:, 1]
    flagged = np.array([p in flags.get(d, set()) for d, p in pages])
    for name, mask in (("random pages", kind == "random"), ("stratified pages", kind == "strat")):
        print(name, int(mask.sum()), "pages,", int(y[mask].sum()), "positive")
        for label, cut in (("extractor alone", 0.0), ("prefilter 0.3 + extractor", 0.3),
                           ("prefilter 0.2 + extractor", 0.2)):
            read = score >= cut  # pages the extractor would read
            print(f"  {label:27s}", prf(y[mask], (flagged & read)[mask]),
                  f"pages read {float(read[mask].mean()):.0%}")


if __name__ == "__main__":
    main()
