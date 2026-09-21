"""Dataset diagnosis — answer 'is 137 training pairs enough?' with numbers.

Reports:
  * class distribution overall and per split (curated labels vs derived pairs)
  * unique commitments / sources per split
  * majority-class baseline accuracy (what guessing 'unrelated' scores)
  * passage length stats
  * near-duplicate passages, especially across splits (leakage check)
  * positives per class — is per-class support learnable at all?

Usage:
    uv run python experiments/diagnose_dataset.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from experiments import common, data  # noqa: E402


def _tokens(text: str) -> set[str]:
    return set(text.lower().split())


def main() -> None:
    coms = data.commitments()
    psgs = data.passages()
    labels = data.labels()
    rows = data.pairs()

    by_src = defaultdict(list)
    for p in psgs:
        by_src[p["source"]].append(p)

    report = {"n_commitments": len(coms), "n_passages": len(psgs),
              "n_sources": len(by_src), "n_curated_labels": len(labels),
              "n_pair_rows": len(rows)}

    # -- class distribution ---------------------------------------------------
    report["curated_relationship"] = dict(
        Counter(l["relationship"] for l in labels))
    report["curated_relevance"] = dict(
        Counter(str(l["relevance"]) for l in labels))

    per_split = defaultdict(Counter)
    for r in rows:
        per_split[r["split"]][r["relationship"]] += 1
    report["pairs_by_split"] = {s: dict(c) for s, c in per_split.items()}

    per_split_com = defaultdict(set)
    per_split_src = defaultdict(set)
    for r in rows:
        per_split_com[r["split"]].add(r["commitment_id"])
        per_split_src[r["split"]].add(r["passage_id"].split("#")[0])
    report["commitments_per_split"] = {s: sorted(v)
                                       for s, v in per_split_com.items()}
    report["sources_per_split"] = {s: sorted(v)
                                   for s, v in per_split_src.items()}

    # -- majority baseline ------------------------------------------------------
    for split in ("train", "val", "test"):
        ys = [r["relationship"] for r in rows if r["split"] == split]
        if ys:
            maj = Counter(ys).most_common(1)[0]
            report[f"majority_{split}"] = {"class": maj[0],
                                           "accuracy": round(maj[1] / len(ys), 4)}

    # -- passage stats ----------------------------------------------------------
    lens = [len(p["text"]) for p in psgs]
    report["passage_chars"] = {"mean": round(sum(lens) / len(lens)),
                               "min": min(lens), "max": max(lens)}

    # -- near-duplicate check (token Jaccard) -----------------------------------
    toks = {p["id"]: _tokens(p["text"]) for p in psgs}
    src_of = {p["id"]: p["source"] for p in psgs}
    dupes = []
    ids = list(toks)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = toks[ids[i]], toks[ids[j]]
            jac = len(a & b) / max(len(a | b), 1)
            if jac >= 0.6:
                dupes.append({
                    "a": ids[i], "b": ids[j], "jaccard": round(jac, 3),
                    "cross_split":
                        data.split_of(src_of[ids[i]])
                        != data.split_of(src_of[ids[j]]),
                })
    report["near_duplicates"] = sorted(dupes, key=lambda d: -d["jaccard"])
    report["cross_split_dupes"] = sum(1 for d in dupes if d["cross_split"])

    # -- per-class learnability ---------------------------------------------------
    train_pos = Counter(r["relationship"] for r in rows
                        if r["split"] == "train"
                        and r["relationship"] != "probably_unrelated")
    report["train_positive_per_class"] = dict(train_pos)
    report["verdict"] = (
        "5-class problem with "
        f"{sum(1 for r in rows if r['split'] == 'train')} train rows; "
        "minority classes have single-digit support — underdetermined."
    )

    common.save_result("diagnose_dataset", report)
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
