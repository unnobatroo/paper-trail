"""Benchmark loading and the leakage-safe split.

Split is by *source document*, not by row: every passage from a given page
lands in exactly one split, so a model can never see near-copies of a test
passage during training. With a corpus this small, some commitments only
have positives in one split — that's a real property of the data, not a bug,
and the report should say so.

    train: most RÉV8 pages, reszvetel_2023, jkit_p45/48/53/64/66, strategy bg
    val:   rev8_danko-utca, jkit_p13/14/15
    test:  rev8_magdolna-kert, rev8_losonci-ter, reszvetel_2024, jkit_p73
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
BENCH = ROOT / "data" / "benchmark"

TEST_SOURCES = {"rev8_magdolna-kert", "rev8_losonci-ter",
                "reszvetel_2024", "jkit_p73"}
VAL_SOURCES = {"rev8_danko-utca", "jkit_p13", "jkit_p14", "jkit_p15"}


def _load(name: str) -> list[dict]:
    return [json.loads(l) for l in (BENCH / name).read_text().splitlines()
            if l.strip()]


def commitments() -> list[dict]:
    return _load("commitments.jsonl")


def passages() -> list[dict]:
    return _load("passages.jsonl")


def labels() -> list[dict]:
    return _load("labels.jsonl")


def split_of(source: str) -> str:
    if source in TEST_SOURCES:
        return "test"
    if source in VAL_SOURCES:
        return "val"
    return "train"


def gold(commitment_id: str, min_rel: int = 1) -> set[str]:
    return {l["passage_id"] for l in labels()
            if l["commitment_id"] == commitment_id and l["relevance"] >= min_rel}


def pairs() -> list[dict]:
    """(commitment, passage, label) rows for reranker/classifier training.

    = every curated label
    + in-source negatives: passages from a source that HAS positives for
      that commitment but were not labelled positive for it
      (hard negatives — same page, wrong claim)
    + one easy negative row per (commitment, source) for sources with no
      labels for that commitment, capped per commitment to keep the
      negative set honest and small.
    """
    coms = commitments()
    psg = passages()
    lab = labels()
    labeled = {(l["commitment_id"], l["passage_id"]): l for l in lab}
    pos_sources = {c["id"]: {l["passage_id"].split("#")[0]
                             for l in lab
                             if l["commitment_id"] == c["id"]
                             and l["relevance"] >= 1}
                   for c in coms}

    rows = [dict(commitment_id=l["commitment_id"], passage_id=l["passage_id"],
                 relevance=l["relevance"], relationship=l["relationship"],
                 split=split_of(l["passage_id"].split("#")[0]))
            for l in lab]
    seen = set(labeled)

    for c in coms:
        cid = c["id"]
        easy = 0
        for p in psg:
            src = p["source"]
            if (cid, p["id"]) in seen:
                continue
            if src in pos_sources[cid]:
                # in-source negative (hard)
                rows.append(dict(commitment_id=cid, passage_id=p["id"],
                                 relevance=0, relationship="probably_unrelated",
                                 split=split_of(src)))
                seen.add((cid, p["id"]))
            elif easy < 6:
                # a few easy negatives per commitment
                rows.append(dict(commitment_id=cid, passage_id=p["id"],
                                 relevance=0, relationship="probably_unrelated",
                                 split=split_of(src)))
                seen.add((cid, p["id"]))
                easy += 1
    return rows
