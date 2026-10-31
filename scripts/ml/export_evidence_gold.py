"""snapshot reviewed evidence into a benchmark corpus + qrels

  DATABASE_URL=<restored backup> uv run python scripts/ml/export_evidence_gold.py data/eval/evidence

writes <prefix>-corpus.json (every evidence passage is a document, every commitment with
evidence a query, same query text the evidence search embeds) and <prefix>-qrels-review.jsonl
(the review decisions as grades). review grades are whatever the ui stored, check them
before trusting: a bulk accept keeps the machine's suggestion
"""
import argparse
import json
import os
from pathlib import Path

from sqlalchemy import text

from paper_trail.repositories.store import engine

GRADES = {"direct_implementation": 3, "budget": 2, "supporting": 2,
          "related_but_indirect": 1, "probably_unrelated": 0}


def export(dsn: str) -> tuple[dict, list[dict]]:
    with engine(dsn).connect() as conn:
        docs = conn.execute(text(
            "SELECT id, url, title, snippet FROM evidence"
            " WHERE coalesce(snippet, '') <> '' ORDER BY id")).mappings().all()
        queries = conn.execute(text(
            "SELECT c.id, c.title, coalesce(c.summary, '') AS summary,"
            " coalesce(c.code, '') AS code FROM commitments c"
            " WHERE EXISTS (SELECT 1 FROM evidence e WHERE e.commitment_id = c.id)"
            " ORDER BY c.id")).mappings().all()
        reviewed = conn.execute(text(
            "SELECT commitment_id, evidence_id, relationship FROM links"
            " WHERE review_status = 'accepted' AND relationship IS NOT NULL"
            " ORDER BY commitment_id, evidence_id")).mappings().all()
    corpus = {
        "documents": [{"id": f"e{d['id']}", "url": d["url"], "title": d["title"],
                       "text": d["snippet"]} for d in docs],
        # same string evidence_service._rank embeds
        "queries": [{"id": f"c{q['id']}", "title": q["title"],
                     "text": " ".join([q["title"], q["summary"], q["code"]])}
                    for q in queries]}
    ids = {d["id"] for d in corpus["documents"]}
    qrels = [{"query": f"c{r['commitment_id']}", "doc": f"e{r['evidence_id']}",
              "grade": GRADES[r["relationship"]], "by": "review"}
             for r in reviewed if f"e{r['evidence_id']}" in ids]
    return corpus, qrels


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prefix", type=Path)
    args = parser.parse_args()
    corpus, qrels = export(os.environ["DATABASE_URL"])
    args.prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{args.prefix}-corpus.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=1))
    Path(f"{args.prefix}-qrels-review.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in qrels))
    print(f"{len(corpus['documents'])} passages, {len(corpus['queries'])} queries, "
          f"{len(qrels)} review judgments")


if __name__ == "__main__":
    main()
