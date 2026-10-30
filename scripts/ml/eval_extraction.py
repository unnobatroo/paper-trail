"""score an llm extractor per document against approved commitments

gold = jsonl, one approved commitment per line:
  {"doc": "jozsefvaros-2021", "pdf": "jozsefvaros_klimastrategia_2021.pdf", "lang": "hu",
   "split": "train" | "holdout", "page": 31, "title": "Távhőszolgáltatás fejlesztése",
   "code": "M1.1.2"}
recall    gold commitments matched by a kept candidate on the same page
kept      candidates whose receipt was verbatim on the page (ingestion keeps only these)
returned  everything the model answered, kept or not

the number that matters is macro recall on holdout docs: a model that only learned
one city's layout scores high on train and falls over there. --export DIR --pdf F
builds gold from a db export (accepted commitments of one strategy) instead.

  uv run python scripts/ml/eval_extraction.py --gold gold.jsonl --docs data/eval \\
    --base-url https://localhost:8443/v1 --model M --key-file K --ca CRT
"""

import argparse
import json
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean

import openai

from paper_trail.ml.client import model_client
from paper_trail.ml.extraction import LLMExtractor
from paper_trail.ml.lang import LanguageProfile
from paper_trail.sources.pdf import read_pages

PROFILES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "profiles"


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


def gold_from_export(export: Path, pdf: Path, lang: str) -> list[dict]:
    rows = [json.loads(line) for line in
            (export / "commitments.jsonl").read_text().splitlines() if line]
    first = {}
    for row in sorted(rows, key=lambda r: r["id"]):
        first.setdefault(row["candidate_id"], row)  # duplicates from double accepts
    return [{"doc": pdf.stem, "pdf": pdf.name, "lang": lang, "split": "train",
             "page": r["source_page"], "title": r["title"], "code": r.get("code")}
            for r in first.values()]


def score_doc(extractor: LLMExtractor, pdf: Path, golds: list[dict]) -> dict:
    by_page = {}
    for g in golds:
        by_page.setdefault(g["page"], []).append(g)
    pages = {p.page_number: p for p in read_pages(pdf)}
    missing = sorted(set(by_page) - set(pages))
    if missing:
        raise SystemExit(f"{pdf.name} has no page(s) {missing}, gold doesn't match the pdf")
    returned = 0
    real_ask = extractor._ask

    def counting_ask(window):
        nonlocal returned
        reply = real_ask(window)
        returned += len(reply.items) if reply else 0
        return reply
    extractor._ask = counting_ask
    numbers = sorted(by_page)
    start = time.monotonic()
    # one extract call over all gold pages, like ingestion, so concurrency shows in wall time
    cands = extractor.extract([pages[n] for n in numbers])
    seconds = time.monotonic() - start
    extractor._ask = real_ask
    found, missed = 0, []
    for number in numbers:
        here = [c for c in cands if c.source_page == number]
        for g in by_page[number]:
            if any(matches(g, c) for c in here):
                found += 1
            else:
                missed.append({"page": number, "title": g["title"]})
    return {"gold": len(golds), "found": found, "recall": round(found / len(golds), 3),
            "kept": len(cands), "returned": returned,
            "receipt_rate": round(len(cands) / returned, 3) if returned else None,
            "seconds_per_page": round(seconds / len(numbers), 1), "missed": missed}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", type=Path)
    ap.add_argument("--docs", type=Path, default=Path("."), help="where gold pdfs live")
    ap.add_argument("--export", type=Path)
    ap.add_argument("--pdf", type=Path)
    ap.add_argument("--lang", default="hu", help="profile for --export gold")
    ap.add_argument("--profiles", type=Path, default=PROFILES, help="dir of <lang>.json")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--ca")
    ap.add_argument("--out")
    ap.add_argument("--concurrency", type=int, default=1)
    args = ap.parse_args()
    if args.ca:
        os.environ["PAPER_TRAIL_MODEL_CA_BUNDLE"] = args.ca
    if args.gold:
        gold = [json.loads(line) for line in args.gold.read_text().splitlines() if line]
    elif args.export and args.pdf:
        gold, args.docs = gold_from_export(args.export, args.pdf, args.lang), args.pdf.parent
    else:
        raise SystemExit("give --gold, or --export with --pdf")

    client = model_client(args.base_url, Path(args.key_file).read_text().strip())
    docs = {}
    for g in gold:
        docs.setdefault(g["doc"], []).append(g)
    per_doc = {}
    for name, golds in docs.items():
        lang = golds[0].get("lang", "hu")
        profile = LanguageProfile.from_dict(
            json.loads((args.profiles / f"{lang}.json").read_text()))
        extractor = LLMExtractor(client, args.model, profile, window=1,
                                 concurrency=args.concurrency)
        try:
            per_doc[name] = score_doc(extractor, args.docs / golds[0]["pdf"], golds)
        except openai.APIError as exc:
            raise SystemExit(f"model server failed on {name}: {exc}") from exc
        per_doc[name]["split"] = golds[0].get("split", "train")
        print(name, json.dumps({k: v for k, v in per_doc[name].items() if k != "missed"}))

    def macro(split):
        vals = [d["recall"] for d in per_doc.values() if d["split"] == split]
        return round(mean(vals), 3) if vals else None
    summary = {"model": args.model, "docs": len(per_doc), "gold": len(gold),
               "recall_micro": round(sum(d["found"] for d in per_doc.values()) / len(gold), 3),
               "recall_macro_train": macro("train"), "recall_macro_holdout": macro("holdout"),
               "concurrency": args.concurrency}
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "docs": per_doc},
                                             indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
