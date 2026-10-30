"""check drafted answer keys against the pdfs, keep only rows whose quote is really there

  uv run python scripts/ml/check_gold.py data/eval/gold-batch-*.jsonl --docs data/eval \\
    --out data/eval/gold.jsonl

a row survives when its quote is verbatim on its page (whitespace aside). failures get
printed so a person can fix or drop them. --sample N prints N random survivors per doc
for the human spot check
"""

import argparse
import json
import random
import re
from pathlib import Path

from paper_trail.sources.pdf import read_pages


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--docs", type=Path, default=Path("data/eval"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sample", type=int, default=0)
    args = ap.parse_args()
    rows = [json.loads(line) for f in args.files for line in f.read_text().splitlines()
            if line.strip()]
    pages: dict[str, list[str]] = {}
    kept, failed = [], []
    for row in rows:
        if row["pdf"] not in pages:
            # same reader ingestion uses, so a kept quote is one the extractor can see
            pages[row["pdf"]] = [squash(p.text) for p in read_pages(args.docs / row["pdf"])]
        text = pages[row["pdf"]]
        on_page = 0 < row["page"] <= len(text)
        if row.get("empty"):
            ok = on_page
        else:
            ok = on_page and squash(row["quote"]) in text[row["page"] - 1]
        (kept if ok else failed).append(row)
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
    by_doc: dict[str, list[int]] = {}
    for r in rows:
        by_doc.setdefault(r["doc"], [0, 0])[0 if r in kept else 1] += 1
    for doc, (ok, bad) in sorted(by_doc.items()):
        print(f"{doc:22} kept {ok:4}  failed {bad:3}")
    for r in failed:
        print(f"FAIL {r['doc']} p{r['page']}: {r.get('quote', '')[:80]!r}")
    for doc in sorted(by_doc) if args.sample else []:
        pool = [r for r in kept if r["doc"] == doc and not r.get("empty")]
        for r in random.Random(0).sample(pool, min(args.sample, len(pool))):
            print(f"CHECK {doc} p{r['page']} [{r.get('code') or '-'}] {r['title_en']}"
                  f"\n      \"{r['quote']}\"")


if __name__ == "__main__":
    main()
