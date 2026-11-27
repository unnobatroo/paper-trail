"""score the extractor page by page against hand-labelled pages (positive / negative / uncertain)

labels: {"<doc>": {"positive": [pages], "negative": [pages], "uncertain": [pages]}}
sample: {"<doc>": {"<page>": "text"}}   (the pages the labels were made from)

A page is predicted positive when the extractor keeps at least one candidate on it.
Uncertain pages are reported but never scored. Intervals are Wilson 95%.

  uv run python scripts/ml/eval_silver_pages.py --labels L.json --sample S.json --lang hu \
    --base-url http://127.0.0.1:8001/v1 --model M --out report.json
"""

import argparse
import json
import math
from pathlib import Path

from paper_trail.domain.models import DocumentPage
from paper_trail.ml.client import model_client
from paper_trail.ml.extraction import LLMExtractor
from paper_trail.ml.lang import LanguageProfile

PROFILES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "profiles"


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - h) / d, 3), round((c + h) / d, 3)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--sample", type=Path, required=True)
    ap.add_argument("--lang", default="hu")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default="local")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    sample = json.loads(args.sample.read_text(encoding="utf-8"))
    profile = LanguageProfile.from_dict(
        json.loads((PROFILES / f"{args.lang}.json").read_text(encoding="utf-8")))
    ex = LLMExtractor(model_client(args.base_url, args.key), args.model, profile, window=1,
                      concurrency=args.concurrency)
    tp = fp = fn = tn = 0
    per_doc = {}
    for doc, lab in ((d, labels[d]) for d in sample if d in labels):
        pages = [DocumentPage(page_number=int(n), text=t) for n, t in sample[doc].items()]
        kept = {c.source_page for c in ex.extract(pages)}
        a = [p for p in lab["positive"] if p in kept]
        b = [p for p in lab["positive"] if p not in kept]
        c = [p for p in lab["negative"] if p in kept]
        d_ = [p for p in lab["negative"] if p not in kept]
        tp, fn, fp, tn = tp + len(a), fn + len(b), fp + len(c), tn + len(d_)
        per_doc[doc] = {"found": len(a), "missed": b, "false_alarm": c,
                        "positives": len(lab["positive"]), "flagged": sorted(kept),
                        "uncertain_flagged": {p: p in kept for p in lab.get("uncertain", [])}}
        print(doc, json.dumps(per_doc[doc]), flush=True)
    report = {"model": args.model, "pages_scored": tp + fn + fp + tn,
              "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
              "precision_ci95": wilson(tp, tp + fp),
              "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
              "recall_ci95": wilson(tp, tp + fn),
              "counts": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, "per_doc": per_doc}
    print(json.dumps({k: v for k, v in report.items() if k != "per_doc"}))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
