"""compare llm extractors against human-accepted commitments, one strategy page per call

gold = commitments a reviewer accepted (one per candidate), on the pages they came from.
recall    gold commitments matched by a kept candidate on the same page
kept      candidates whose receipt was verbatim on the page (ingestion keeps only these)
returned  everything the model answered, kept or not

  uv run python scripts/ml/eval_extraction.py --export DIR --pdf strategy.pdf \\
    --base-url https://localhost:8443/v1 --model Qwen/Qwen3-4B-AWQ --key-file K --ca CRT
"""

import argparse
import json
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests

from paper_trail.ml.extraction import LLMExtractor
from paper_trail.sources.pdf import read_pages
from tests.profiles import HU


def norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def matches(gold: dict, cand) -> bool:
    title, code = norm(gold["title"]), norm(gold.get("code") or "")
    hay = norm(f"{cand.text} {cand.normalized_title} {cand.source_excerpt}")
    if title and title in hay:
        return True
    if code and re.search(rf"\b{re.escape(code)}\b", hay) and len(code) > 1:
        return True
    return SequenceMatcher(None, title, norm(cand.normalized_title)).ratio() >= 0.6


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--ca")
    ap.add_argument("--out")
    ap.add_argument("--concurrency", type=int, default=1)
    args = ap.parse_args()
    if args.ca:
        os.environ["PAPER_TRAIL_MODEL_CA_BUNDLE"] = args.ca

    rows = [json.loads(line) for line in
            Path(args.export, "commitments.jsonl").read_text().splitlines() if line]
    gold = {}
    for row in sorted(rows, key=lambda r: r["id"]):
        gold.setdefault(row["candidate_id"], row)
    by_page = {}
    for row in gold.values():
        by_page.setdefault(row["source_page"], []).append(row)
    pages = {p.page_number: p for p in read_pages(args.pdf)}
    key = Path(args.key_file).read_text().strip()
    extractor = LLMExtractor(args.base_url, key, args.model, HU, window=1,
                             concurrency=args.concurrency)

    found = kept = returned = errors = 0
    per_page = []
    raw = {}
    real_ask = extractor._ask

    def counting_ask(window):
        nonlocal returned
        reply = real_ask(window)
        returned += len(reply.items) if reply else 0
        # keep every answer, kept or not, to explain misses
        raw[window[0].page_number] = None if reply is None else [
            i.model_dump() for i in reply.items]
        return reply
    extractor._ask = counting_ask
    # one extract call over all gold pages, like ingestion, so concurrency shows in wall time
    numbers = sorted(by_page)
    start = time.monotonic()
    try:
        cands_all = extractor.extract([pages[n] for n in numbers])
    except requests.RequestException as exc:
        raise SystemExit(f"model server failed: {exc}") from exc
    seconds = time.monotonic() - start
    for number in numbers:
        golds = by_page[number]
        cands = [c for c in cands_all if c.source_page == number]
        hit = [g for g in golds if any(matches(g, c) for c in cands)]
        found += len(hit)
        kept += len(cands)
        per_page.append({
            "page": number, "gold": len(golds), "found": len(hit), "kept": len(cands),
            "missed": [g["title"] for g in golds if g not in hit],
            "kept_titles": [c.normalized_title for c in cands],
            "answer": raw.get(number)})
    total = len(gold)
    summary = {
        "model": args.model, "pages": len(by_page), "gold": total,
        "recall": round(found / total, 3), "kept": kept, "returned": returned,
        "receipt_rate": round(kept / returned, 3) if returned else None,
        "seconds_per_page": round(seconds / len(by_page), 1),
        "concurrency": args.concurrency,
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "pages": per_page},
                                             indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
