"""score the extractor on Climate Policy Radar's national-climate-targets passages

External benchmark: 2,610 expert-labelled passages from national laws and policies in
192 geographies (906 machine-translated to English), CC-BY-4.0. A passage is positive when
it holds a target (quantified, with a deadline): net zero, reduction or other.
https://huggingface.co/datasets/ClimatePolicyRadar/national-climate-targets

The extractor reads each passage as one page. It predicts "target" when it keeps at least
one candidate, so this scores the detection step, not the wording of the answers. Our
commitment definition is wider than a quantified target, so precision here is a floor.

Splits are grouped by geography (a country never sits in both dev and test), fixed by a
seed. Tune on dev, report test once. Confidence intervals are bootstrap over passages.
A regex baseline (a year plus a number or percent) shows what the model has to beat.

  uv run --with pyarrow python scripts/ml/eval_cpr_targets.py --parquet data/eval_ext/... \\
    --base-url http://127.0.0.1:8001/v1 --model M --key local --out report.json
"""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

import pandas as pd

from paper_trail.domain.models import DocumentPage
from paper_trail.ml.client import model_client
from paper_trail.ml.extraction import LLMExtractor
from paper_trail.ml.lang import LanguageProfile

PROFILES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "profiles"
LABELS = ("annotation_NZT", "annotation_Reduction", "annotation_Other")
YEAR = re.compile(r"\b(19|20)\d{2}\b")
QUANT = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|per ?cent|percent|MW|GW|Mt|kt|tonnes?)|net[- ]zero|carbon neutral",
    re.I)


def load(parquet: Path) -> pd.DataFrame:
    d = pd.read_parquet(parquet).reset_index(drop=True)
    d["id"] = d.index
    d["positive"] = d[list(LABELS)].sum(axis=1) > 0
    return d


def in_test(geography: str, seed: int) -> bool:
    """stable per-geography coin flip, independent of row order and of pandas versions"""
    return hashlib.sha256(f"{seed}:{geography}".encode()).digest()[0] % 2 == 1


def baseline(text: str) -> bool:
    return bool(YEAR.search(text) and QUANT.search(text))


def metrics(gold: list[bool], pred: list[bool]) -> dict:
    tp = sum(g and p for g, p in zip(gold, pred, strict=True))
    fp = sum(p and not g for g, p in zip(gold, pred, strict=True))
    fn = sum(g and not p for g, p in zip(gold, pred, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def bootstrap(gold: list[bool], pred: list[bool], n: int = 1000, seed: int = 0) -> dict:
    """95% percentile interval per metric, resampling passages with replacement"""
    rng = random.Random(seed)
    rows = list(zip(gold, pred, strict=True))
    runs = []
    for _ in range(n):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        runs.append(metrics([g for g, _ in sample], [p for _, p in sample]))
    out = {}
    for key in ("precision", "recall", "f1"):
        vals = sorted(r[key] for r in runs)
        out[key] = [round(vals[int(0.025 * n)], 3), round(vals[int(0.975 * n)], 3)]
    return out


def report(name: str, frame: pd.DataFrame, col: str) -> dict:
    gold, pred = frame.positive.tolist(), frame[col].tolist()
    m = {k: round(v, 3) for k, v in metrics(gold, pred).items()}
    return {"system": name, "n": len(frame), "positives": int(sum(gold)), **m,
            "ci95": bootstrap(gold, pred)}


def predict(d: pd.DataFrame, args) -> dict[int, bool | None]:
    """one extractor call per passage; answers are cached so a crash resumes. an answer is
    reused only for the same model and the same passage text, so another model or a changed
    dataset never reads a stale one"""
    stamp = {int(i): hashlib.sha256(f"{args.model}|{t}".encode()).hexdigest()[:16]
             for i, t in zip(d.id, d.text, strict=True)}
    cache = {}
    if args.cache.exists():
        for row in map(json.loads, args.cache.read_text().splitlines()):
            if stamp.get(row["id"]) == row.get("stamp"):
                cache[row["id"]] = row["kept"]
    todo = d[~d.id.isin(cache)]
    if len(todo):
        client = model_client(args.base_url, args.key)
        profile = LanguageProfile.from_dict(json.loads((PROFILES / "en.json").read_text()))
        ex = LLMExtractor(client, args.model, profile, window=1, concurrency=args.concurrency)
        with args.cache.open("a") as f:
            for start in range(0, len(todo), 40):
                chunk = todo.iloc[start:start + 40]
                # page_number = row id, so each candidate maps back to its passage
                pages = [DocumentPage(page_number=int(i) + 1, text=t)
                         for i, t in zip(chunk.id, chunk.text, strict=True)]
                finished, kept = set(), set()
                for done, cands in ex.extract_windows(pages):
                    finished |= {p.page_number for p in done}
                    kept |= {c.source_page for c in cands}
                for i in chunk.id:
                    if (int(i) + 1) not in finished:
                        cache[int(i)] = None  # unreadable answer: not scored, asked again next run
                        continue
                    cache[int(i)] = (int(i) + 1) in kept
                    row = {"id": int(i), "kept": cache[int(i)], "stamp": stamp[int(i)]}
                    f.write(json.dumps(row) + "\n")
                f.flush()
                print(f"{len(cache)}/{len(d)}", flush=True)
    return cache


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", type=Path, required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--key", default="local")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--split", choices=("dev", "test", "all"), default="test")
    ap.add_argument("--limit", type=int, help="first N passages of the split, for smoke runs")
    ap.add_argument("--cache", type=Path, default=Path("data/eval_ext/cpr_predictions.jsonl"))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    d = load(args.parquet)
    d["test"] = [in_test(g, args.seed) for g in d.geography]
    if args.split != "all":
        d = d[d.test == (args.split == "test")]
    if args.limit:
        d = d.head(args.limit)
    d = d.copy()
    preds = predict(d, args)
    # a passage the model never answered is left out for both systems, not scored as a miss
    unread = int(sum(preds[int(i)] is None for i in d.id))
    if unread:
        print(f"{unread} passages had no usable answer and are excluded; run again to retry")
    d = d[[preds[int(i)] is not None for i in d.id]].copy()
    d["model"] = [preds[int(i)] for i in d.id]
    d["regex"] = [baseline(t) for t in d.text]

    results = {"split": args.split, "seed": args.seed, "model": args.model,
               "unread_passages_excluded": unread,
               "geographies": int(d.geography.nunique()),
               "overall": [report("model", d, "model"), report("regex baseline", d, "regex")],
               "translated": {str(flag): report("model", sub, "model")
                              for flag, sub in d.groupby("translated")}}
    for r in results["overall"]:
        print(json.dumps(r))
    if args.out:
        args.out.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
