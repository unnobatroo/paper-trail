"""reviewed candidates -> chat sft jsonl for the extraction model

one example per page, prompt built by the same extraction_prompt the server uses, answer
in the same json the extractor parses. a person decided every label:
  accepted candidate -> an item (title/kind from the commitment if someone edited it)
  page with only rejects -> {"items": []}, teaches the model to keep its mouth shut
  page nobody reviewed -> skipped, unknown isn't empty
documents in --holdout never get in, those are the eval's.
--gold adds checked answer keys (check_gold.py output) of other cities, train split only

  DATABASE_URL=... uv run python scripts/ml/finetune/build_dataset.py \\
    --doc 2=data/source_documents/jozsefvaros_klimastrategia_2021.pdf --out train.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

from paper_trail.bootstrap import load_profile
from paper_trail.domain.enums import ReviewStatus
from paper_trail.ml.extraction import KINDS, PAGE_CHARS, extraction_prompt, squash
from paper_trail.repositories.store import PolicyRepository
from paper_trail.sources.pdf import read_pages


def shown(page, excerpt: str) -> bool:
    # the prompt cuts pages at PAGE_CHARS, a label past that teaches the model to make stuff up
    return bool(excerpt.strip()) and squash(excerpt) in squash(page.text[:PAGE_CHARS])


def examples(repo, profile, doc_id: int, pdf: Path) -> list[dict]:
    cands = [c for c in repo.candidates() if c.document_id == doc_id]
    edited = {m.candidate_id: m for m in repo.commitments() if m.candidate_id}
    by_page: dict[int, list] = {}
    for c in cands:
        by_page.setdefault(c.source_page, []).append(c)
    pages = {p.page_number: p for p in read_pages(pdf)}
    out = []
    for number, decided in sorted(by_page.items()):
        # one open candidate = the page isn't fully labelled, its answer would miss stuff
        if any(c.review_status == ReviewStatus.UNREVIEWED for c in decided):
            continue
        if number not in pages:
            print(f"doc {doc_id}: page {number} not in {pdf.name}, skipped", file=sys.stderr)
            continue
        items = []
        for c in decided:
            if c.review_status != ReviewStatus.ACCEPTED or not c.source_excerpt:
                continue
            com = edited.get(c.id)
            kind = com.kind if com else c.suggested_type
            # background/unclear get dropped by extract anyway, don't teach them
            if kind not in KINDS or not shown(pages[number], c.source_excerpt[:300]):
                continue
            items.append({"type": kind.value,
                          "normalized_title": (com.title if com else c.normalized_title)[:120],
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
        page = cache[pdf].get(number)
        if page is None:
            print(f"{doc}: page {number} not in {pdf}, skipped", file=sys.stderr)
            continue
        profile = LanguageProfile.from_dict(json.loads((profiles / f"{lang}.json").read_text()))
        # gold has no commitment sentence, the quote beats the heading as `text`
        items = [{"type": g["kind"], "normalized_title": g["title"][:120],
                  "text": g["quote"][:400], "page": number, "excerpt": g["quote"][:300]}
                 for g in golds if not g.get("empty") and shown(page, g["quote"][:300])]
        out.append({"doc": doc, "page": number, "messages": [
            {"role": "user", "content": extraction_prompt(profile, [page])},
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
    if not args.doc and not args.gold:
        ap.error("nothing to build from, pass --doc and/or --gold")
    from paper_trail.settings import load
    settings = load()
    repo = PolicyRepository(settings.database_url)
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
