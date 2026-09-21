"""Why does stage-1 retrieval miss gold passages?

For every labelled gold passage (relevance >= 1) that MiniLM fails to
place in the top-K candidate set, categorize the miss:

    beyond_60kb        production would never embed it (JKIT pages >= 48)
    straddles_60kb     starts just under the cap, mostly cut (jkit_p45)
    low_semantic_sim   cosine < 0.40 — real embedding failure
    just_missed        rank 11..K*2 — fixed by a wider candidate set
    weak_rank          rank > K*2 — corpus competition, needs rerank depth

The 60 KB boundary was measured against the JKIT PDF: page 48 starts at
62 KB, page 45 at 58 KB. All web sources are < 19 KB — the cap only bites
the implementation report, which is exactly where the evidence lives.

Usage:
    uv run python experiments/diagnose_retrieval.py
    uv run python experiments/diagnose_retrieval.py --k 10
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from experiments import common, data  # noqa: E402

BEYOND_60KB = {"jkit_p48", "jkit_p53", "jkit_p64", "jkit_p66", "jkit_p73"}
STRADDLES = {"jkit_p45"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    rows = json.loads((common.RESULTS / "pair_features.json")
                      .read_text())["rows"]
    psgs = {p["id"]: p for p in data.passages()}
    notes = {(l["commitment_id"], l["passage_id"]): l.get("note", "")
             for l in data.labels()}

    by_c = defaultdict(list)
    for r in rows:
        by_c[r["commitment_id"]].append(r)
    rank = {}
    for cid, rs in by_c.items():
        rs.sort(key=lambda r: -r["sim"])
        for i, r in enumerate(rs, 1):
            rank[(cid, r["passage_id"])] = i

    gold = [r for r in rows if (r["label_relevance"] or 0) >= 1]
    missed = [r for r in gold
              if rank[(r["commitment_id"], r["passage_id"])] > args.k]

    cats = Counter()
    detail = defaultdict(list)
    for r in missed:
        cid, pid = r["commitment_id"], r["passage_id"]
        rk = rank[(cid, pid)]
        if r["source"] in BEYOND_60KB:
            cat = "beyond_60kb"
        elif r["source"] in STRADDLES:
            cat = "straddles_60kb"
        elif r["sim"] < 0.40:
            cat = "low_semantic_sim"
        elif rk <= args.k * 2:
            cat = "just_missed"
        else:
            cat = "weak_rank"
        cats[cat] += 1
        detail[cat].append({
            "passage_id": pid, "commitment_id": cid, "rank": rk,
            "sim": r["sim"], "ce_pretrained": r["ce_pretrained"],
            "note": notes.get((cid, pid), ""),
            "text": psgs[pid]["text"][:200],
        })

    report = {
        "k": args.k, "n_gold": len(gold), "n_missed": len(missed),
        "recall_ceiling": round((len(gold) - len(missed)) / len(gold), 3),
        "categories": dict(cats),
        "detail": dict(detail),
    }
    common.save_result("diagnose_retrieval", report)
    print(f"gold={len(gold)} missed@{args.k}={len(missed)} "
          f"ceiling={report['recall_ceiling']}")
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")
        for it in detail[cat][:2]:
            print(f"    rk={it['rank']} sim={it['sim']} "
                  f"ce={round(it['ce_pretrained'],2)} {it['passage_id']} "
                  f"| {it['note'][:60]}")


if __name__ == "__main__":
    main()
