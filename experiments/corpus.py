"""Rebuilt corpora + propagated labels, cached as JSON.

chunking_study explores variants; downstream scripts (query_study,
candidate_sweep, pipeline eval) load one frozen corpus so everyone
measures on identical chunks and labels.

Corpus row: {id, source, split, lo, hi, text}
Labels:     {(commitment_id, chunk_id): relevance}

Usage:
    from experiments import corpus
    chunks, relevance = corpus.load("fixed_2400")
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from experiments import common, data
from experiments.build_benchmark import SOURCES, JKIT, STRATEGY, RAW, _URLS
from experiments.chunking_study import CHUNKERS, _norm
from paper_trail.sources.pdf import read_pages

CACHE = common.RESULTS


def _source_texts() -> dict[str, tuple[str, str]]:
    jkit = read_pages(JKIT)
    strat = read_pages(STRATEGY)
    out = {}
    for key, kind, loc in SOURCES:
        if kind == "raw":
            out[key] = ((RAW / loc).read_text(encoding="utf-8"),
                        _URLS.get(key, ""))
        else:
            pages = jkit if kind == "jkit" else strat
            out[key] = (pages[loc - 1].text, "")
    return out


def build(name: str) -> Path:
    chunker = CHUNKERS[name]
    texts = _source_texts()
    labels = data.labels()

    gold_spans = defaultdict(list)
    for l in labels:
        src, idx = l["passage_id"].split("#")
        gold_spans[src].append((int(idx) * 800, int(idx) * 800 + 800,
                                l["commitment_id"], l["relevance"]))

    chunks = []
    relevance = {}
    for src, (text, url) in texts.items():
        for i, (lo, hi, chunk) in enumerate(chunker(text)):
            cid_ = f"{src}#{i}"
            chunks.append({"id": cid_, "source": src,
                           "split": data.split_of(src),
                           "lo": lo, "hi": hi, "url": url,
                           "text": chunk})
            for (glo, ghi, cid, rel) in gold_spans[src]:
                ov = max(0, min(hi, ghi) - max(lo, glo))
                if ov >= 0.5 * (ghi - glo):
                    if rel > relevance.get((cid, cid_), 0):
                        relevance[(cid, cid_)] = rel

    out = CACHE / f"corpus_{name}.json"
    out.write_text(json.dumps({
        "chunker": name,
        "chunks": chunks,
        "relevance": {f"{c}|{p}": r for (c, p), r in relevance.items()},
    }, ensure_ascii=False))
    return out


def load(name: str):
    path = CACHE / f"corpus_{name}.json"
    if not path.exists():
        path = build(name)
    d = json.loads(path.read_text())
    relevance = {}
    for k, v in d["relevance"].items():
        c, p = k.split("|", 1)
        relevance[(c, p)] = v
    return d["chunks"], relevance
