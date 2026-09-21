"""Error analysis — dump representative failures with passage text.

For every test pair row: true label, heuristic prediction, scores, and
where each method disagreed. Categories are assigned mechanically where
possible (promise-vs-implementation needs a human read; we surface the
candidates, not a verdict).

Output: experiments/results/error_analysis_*.json — read it, don't
trust it to categorise itself.

Usage:
    uv run python experiments/error_analysis.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, data  # noqa: E402

ROWS = json.loads((common.RESULTS / "pair_features.json")
                  .read_text())["rows"]


def main() -> None:
    psgs = {p["id"]: p for p in data.passages()}
    coms = {c["id"]: c for c in data.commitments()}
    lab_notes = {(l["commitment_id"], l["passage_id"]): l.get("note", "")
                 for l in data.labels()}

    test = [r for r in ROWS
            if r["pair_split"] == "test" and r["pair_relationship"]]

    buckets = defaultdict(list)
    for r in test:
        true = r["pair_relationship"]
        heur = r["heuristic_rel"]
        is_pos = (r["pair_relevance"] or 0) >= 1
        heur_pos = heur != "probably_unrelated"
        ce_pos = (r["ce_pretrained"] or -9) > 0

        cats = []
        if is_pos and not heur_pos:
            cats.append("missed_evidence")
        if not is_pos and heur_pos:
            cats.append("false_positive")
        if is_pos and heur_pos and true != heur:
            cats.append("wrong_relationship")
        if is_pos and not ce_pos:
            cats.append("ce_missed")
        if not is_pos and ce_pos:
            cats.append("ce_false_positive")
        if not cats:
            continue

        p = psgs[r["passage_id"]]
        c = coms[r["commitment_id"]]
        buckets["+".join(cats)].append({
            "commitment": f'{c["id"]}: {c["title"][:80]}',
            "passage_id": r["passage_id"], "source": r["source"],
            "true": true, "heuristic": heur,
            "sim": r["sim"], "ce": r["ce_pretrained"],
            "ce_ft": r["ce_finetuned"],
            "note": lab_notes.get((r["commitment_id"], r["passage_id"]), ""),
            "text": p["text"][:400],
        })

    out = {"n_test": len(test),
           "n_errors": sum(len(v) for v in buckets.values()),
           "by_category": {k: v for k, v in sorted(buckets.items())}}
    common.save_result("error_analysis", out)
    for k, v in sorted(buckets.items()):
        print(f"{k}: {len(v)}")


if __name__ == "__main__":
    main()
