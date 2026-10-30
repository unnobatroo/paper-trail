"""reviewed candidates -> chat sft jsonl for the extraction model

one example per page, prompt built by the same extraction_prompt the server uses, answer
in the same json the extractor parses. a person decided every label:
  accepted candidate -> an item (title/kind from the commitment if someone edited it)
  page with only rejects -> {"items": []}, teaches the model to keep its mouth shut
  page nobody reviewed -> skipped, unknown isn't empty
documents in --holdout never get in, those are the eval's.
--gold adds checked answer keys (check_gold.py output) of other cities, train split only

  PAPER_TRAIL_DATABASE_URL=... uv run python scripts/ml/finetune/build_dataset.py \\
    --doc 2=data/source_documents/jozsefvaros_klimastrategia_2021.pdf --out train.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

from paper_trail.bootstrap import load_profile
from paper_trail.domain.enums import ReviewStatus
from paper_trail.ml.extraction import extraction_prompt
from paper_trail.repositories.store import PolicyRepository
from paper_trail.sources.pdf import read_pages


def examples(repo, profile, doc_id: int, pdf: Path) -> list[dict]:
    cands = [c for c in repo.candidates() if c.document_id == doc_id]
    edited = {m.candidate_id: m for m in repo.commitments() if m.candidate_id}
    by_page: dict[int, list] = {}
    for c in cands:
        if c.review_status != ReviewStatus.UNREVIEWED:
            by_page.setdefault(c.source_page, []).append(c)
    pages = {p.page_number: p for p in read_pages(pdf)}
    out = []
    for number, decided in sorted(by_page.items()):
        if number not in pages:
            print(f"doc {doc_id}: page {number} not in {pdf.name}, skipped", file=sys.stderr)
            continue
        items = []
        for c in decided:
            if c.review_status != ReviewStatus.ACCEPTED or not c.source_excerpt:
                continue
            com = edited.get(c.id)
            items.append({"type": (com.kind if com else c.suggested_type).value,
                          "normalized_title": com.title if com else c.normalized_title,
                          "text": c.text[:400], "page": number,
                          "excerpt": c.source_excerpt[:300]})
        out.append({"doc": doc_id, "page": number, "messages": [
            {"role": "user", "content": extraction_prompt(profile, [pages[number]])},
            {"role": "assistant", "content": json.dumps({"items": items}, ensure_ascii=False)},
        ]})
    return out


def gold_examples(rows: list[dict], docs: Path, profiles: Path) -> list[dict]:
    """train-split answer keys -> the same examples, one per page they cover"""
    from paper_trail.ml.lang import LanguageProfile
    by_page: dict[tuple, list[dict]] = {}
    for r in rows:
        if r.get("split") == "train":
            by_page.setdefault((r["doc"], r["pdf"], r["lang"], r["page"]), []).append(r)
    out, cache = [], {}
    for (doc, pdf, lang, number), golds in sorted(by_page.items()):
        if pdf not in cache:
            cache[pdf] = {p.page_number: p for p in read_pages(docs / pdf)}
        profile = LanguageProfile.from_dict(json.loads((profiles / f"{lang}.json").read_text()))
        items = [{"type": g["kind"], "normalized_title": g["title"], "text": g["title"],
                  "page": number, "excerpt": g["quote"]} for g in golds if not g.get("empty")]
        out.append({"doc": doc, "page": number, "messages": [
            {"role": "user", "content": extraction_prompt(profile, [cache[pdf][number]])},
            {"role": "assistant", "content": json.dumps({"items": items}, ensure_ascii=False)},
        ]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", action="append", default=[], metavar="ID=PDF",
                    help="document id in the db and its pdf, repeatable")
    ap.add_argument("--holdout", action="append", type=int, default=[], metavar="ID")
    ap.add_argument("--language", default="hu")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--gold", type=Path, help="checked answer keys, train rows get used")
    ap.add_argument("--gold-docs", type=Path, default=Path("data/eval"))
    ap.add_argument("--profiles", type=Path,
                    default=Path(__file__).resolve().parents[3] / "tests/fixtures/profiles")
    args = ap.parse_args()
    from paper_trail.infrastructure.settings import load
    settings = load()
    repo = PolicyRepository(settings.database_url or settings.db_path)
    profile = load_profile(repo, args.language)
    rows = []
    for spec in args.doc:
        doc_id, pdf = spec.split("=", 1)
        if int(doc_id) in args.holdout:
            continue  # eval docs never leak into training
        rows += examples(repo, profile, int(doc_id), Path(pdf))
    if args.gold:
        gold = [json.loads(line) for line in args.gold.read_text().splitlines() if line.strip()]
        rows += gold_examples(gold, args.gold_docs, args.profiles)
    with args.out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    empty = sum(1 for r in rows if r["messages"][1]["content"] == '{"items": []}')
    print(f"{len(rows)} pages ({empty} with nothing to extract) -> {args.out}")


if __name__ == "__main__":
    main()
