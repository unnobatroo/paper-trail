"""Chunking study — is the fixed 800/1200-char window losing evidence?

Rebuilds the corpus from the same raw sources under different chunking
schemes, propagates gold labels by character-offset overlap (a chunk is
gold for a commitment if it covers >= 50% of a labelled passage's span),
then evaluates retrieval for each (chunker x model).

Variants: fixed_800 (benchmark), fixed_1200 (production size),
overlap_1200_400, paragraph_1200 (newline-aware merge), fixed_2400.

Usage:
    uv run --group ml python experiments/chunking_study.py
    uv run --group ml python experiments/chunking_study.py \
        --models sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, data, metrics  # noqa: E402
from experiments.build_benchmark import SOURCES, JKIT, STRATEGY, RAW  # noqa: E402
from paper_trail.sources.pdf import read_pages  # noqa: E402

MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-large-instruct",
]


# --------------------------------------------------------------------------
# chunkers: return list of (start, end, text) spans over normalized text

def _norm(t: str) -> str:
    return " ".join(t.split())


def fixed(n: int, stride: int | None = None):
    stride = stride or n
    def f(text: str):
        t = _norm(text)
        return [(i, min(i + n, len(t)), t[i:i + n])
                for i in range(0, len(t), stride)]
    return f


def paragraph(max_chars: int):
    def f(text: str):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        spans, buf, off = [], "", 0
        for line in lines:
            cand = (buf + " " + line).strip()
            if len(cand) > max_chars and buf:
                spans.append((off, off + len(buf), buf))
                off += len(buf) + 1
                buf = line
            else:
                buf = cand
        if buf:
            spans.append((off, off + len(buf), buf))
        return spans
    return f


CHUNKERS = {
    "fixed_800": fixed(800),
    "fixed_1200": fixed(1200),
    "overlap_1200_400": fixed(1200, stride=800),
    "paragraph_1200": paragraph(1200),
    "fixed_2400": fixed(2400),
}


def _source_texts() -> dict[str, tuple[str, str]]:
    """source_key -> (normalized-ish raw text, url)."""
    from experiments.build_benchmark import _URLS
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args()

    texts = _source_texts()
    labels = data.labels()
    # gold spans per source: original 800-char chunks
    gold_spans = defaultdict(list)  # source -> [(lo, hi, cid, rel)]
    for l in labels:
        src, idx = l["passage_id"].split("#")
        lo = int(idx) * 800
        hi = lo + 800
        gold_spans[src].append((lo, hi, l["commitment_id"],
                                l["relevance"], l["relationship"]))

    coms = data.commitments()
    queries = [f'{c["title"]} {c["text"]}' for c in coms]

    from sentence_transformers import SentenceTransformer
    import numpy as np

    models = {m: SentenceTransformer(m.strip(), device=common.device())
              for m in args.models.split(",") if m.strip()}
    qv = {m: models[m].encode(queries, normalize_embeddings=True)
          for m in models}

    report = {}
    for cname, chunker in CHUNKERS.items():
        corpus, meta = [], []
        for src, (text, url) in texts.items():
            for i, (lo, hi, chunk) in enumerate(chunker(text)):
                corpus.append(chunk)
                meta.append({"id": f"{src}#{i}", "source": src,
                             "lo": lo, "hi": hi})
        # propagate labels: chunk inherits a gold label if it covers
        # >=50% of the gold span. Also track WHICH original gold spans
        # each new chunk covers, for a fair cross-chunker metric.
        relevance = {}
        covers = defaultdict(set)   # chunk meta idx -> {(cid, src, gi)}
        gold_total = defaultdict(set)  # cid -> {(cid, src, gi)}
        for mi, m in enumerate(meta):
            for gi, (glo, ghi, cid, rel, relship) in enumerate(
                    gold_spans[m["source"]]):
                ov = max(0, min(m["hi"], ghi) - max(m["lo"], glo))
                if ov >= 0.5 * (ghi - glo):
                    key = (cid, m["id"])
                    if rel > relevance.get(key, 0):
                        relevance[key] = rel
                    if rel >= 1:
                        covers[mi].add((cid, m["source"], gi))
                        gold_total[cid].add((cid, m["source"], gi))

        for mname, model in models.items():
            with common.Timer() as t:
                pv = model.encode(corpus, normalize_embeddings=True,
                                  batch_size=32)
                sims = np.asarray(qv[mname]) @ np.asarray(pv).T
            ranked = {}
            for qi, c in enumerate(coms):
                order = np.argsort(-sims[qi])
                ranked[c["id"]] = [meta[j]["id"] for j in order]
            rep = metrics.ranking_report(ranked, relevance,
                                       k_list=(5, 10, 20))
            # gold-span coverage@10: fraction of each commitment's
            # original gold spans covered by ANY top-10 chunk — the same
            # gold set for every chunker, so comparable.
            covs = []
            for qi, c in enumerate(coms):
                top = set(np.argsort(-sims[qi])[:10])
                covered = set()
                for mi in top:
                    covered |= covers.get(mi, set())
                covered &= gold_total[c["id"]]
                covs.append(len(covered) / len(gold_total[c["id"]])
                            if gold_total[c["id"]] else 0.0)
            rep["gold_cov@10"] = round(sum(covs) / len(covs), 4)
            rep["n_chunks"] = len(corpus)
            rep["embed_s"] = t.seconds
            report[f"{cname} | {mname}"] = rep
            print(f"{cname:18s} {mname.split('/')[-1]:44s} "
                  f"n={len(corpus):3d} r@5={rep['recall@5']:.3f} "
                  f"r@10={rep['recall@10']:.3f} r@20={rep['recall@20']:.3f} "
                  f"cov@10={rep['gold_cov@10']:.3f} "
                  f"ndcg={rep['ndcg@10']:.3f} mrr={rep['mrr']:.3f} "
                  f"({rep['embed_s']}s)")

    common.save_result("chunking_study", {"results": report})


if __name__ == "__main__":
    main()
