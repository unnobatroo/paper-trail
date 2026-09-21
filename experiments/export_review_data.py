"""Export human review decisions as benchmark rows.

Every accepted/rejected evidence link in the app DB becomes a labelled
(commitment, passage, label) row — this is how the benchmark grows: real
review work, not generated labels. Run after a review session, append to
data/benchmark/ manually after eyeballing the output.

Row schema matches data.pairs(): commitment_id, passage_id, source,
relevance, relationship, plus reviewer_decision and the heuristic's own
suggestion for audit.

Relevance mapping (conservative):
    accepted + direct_implementation            -> 2
    accepted + supporting/budget/indirect       -> 1
    rejected                                    -> 0

Usage:
    uv run python experiments/export_review_data.py \
        --db data/processed/paper_trail.db --out data/benchmark/reviewed.jsonl
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, ".")

RELEVANCE = {
    "direct_implementation": 2,
    "supporting": 1,
    "budget": 1,
    "related_but_indirect": 1,
    "probably_unrelated": 0,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/processed/paper_trail.db")
    ap.add_argument("--out", default="data/benchmark/reviewed.jsonl")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT l.id, l.review_status, l.relationship,
                  l.suggested_relationship, l.score,
                  c.id AS commitment_pk, c.code, c.title AS ctitle,
                  e.url, e.title AS etitle, e.snippet
           FROM links l
           JOIN commitments c ON c.id = l.commitment_id
           JOIN evidence e ON e.id = l.evidence_id
           WHERE l.review_status != 'unreviewed'
           ORDER BY l.id""").fetchall()

    out = Path(args.out)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            decided = r["review_status"] == "accepted"
            rel_label = r["relationship"] or r["suggested_relationship"]
            rec = {
                "commitment_id": r["code"] or f"db:{r['commitment_pk']}",
                "commitment_title": r["ctitle"],
                "passage_text": r["snippet"],
                "source": r["url"],
                "passage_title": r["etitle"],
                "reviewer_decision": r["review_status"],
                "relationship": rel_label,
                "relevance": RELEVANCE.get(rel_label, 0) if decided else 0,
                "suggested_relationship": r["suggested_relationship"],
                "heuristic_score": r["score"],
                "note": "",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} reviewed rows -> {out}")
    if n == 0:
        print("no reviewed links yet — review some evidence in the app first")


if __name__ == "__main__":
    main()
