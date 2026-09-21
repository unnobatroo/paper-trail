"""Benchmark the EXACT production retrieval pipeline.

    multilingual-e5-large embeddings (as shipped via fastembed;
        evaluated here through sentence-transformers — same weights,
        ONNX vs torch runtime may differ by a rounding hair)
    → 2400-char chunks (corpus_fixed_2400)
    → top-20 cosine candidates
    → cross-encoder rerank: jina-v2-base-multilingual (production
      default) vs BGE-reranker-v2-m3 (optional provider)
    → best chunk per source document
    → top-5 proposed sources

Metrics reported two ways:
    chunk level  — r@k/p@k/MRR/nDCG on the proposed chunk ranking
    source level — a source counts if ANY of its chunks is gold for the
                   commitment (what the reviewer actually sees)

Usage:
    uv run --group ml python experiments/evaluate_production.py
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, corpus, data, metrics  # noqa: E402

EMBED = "intfloat/multilingual-e5-large"
K_CANDIDATES = 20
TOP_SOURCES = 5
RERANKERS = {
    "jinaai/jina-reranker-v2-base-multilingual": "fastembed",
    "BAAI/bge-reranker-v2-m3": "st",
}


def _load_ce(model: str, kind: str):
    if kind == "fastembed":
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        m = TextCrossEncoder(model_name=model)
        return lambda q, docs: [float(s) for s in m.rerank(q, docs)]
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(model, device=common.device())
    return lambda q, docs: [float(s) for s in
                            m.predict([[q, d] for d in docs])]


def main() -> None:
    chunks, relevance = corpus.load("fixed_2400")
    coms = data.commitments()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]
    srcs = [c["source"] for c in chunks]

    # source-level gold: any gold chunk on that source for the commitment
    src_gold = defaultdict(set)
    for (cid, pid), rel in relevance.items():
        if rel >= 1:
            src = pid.split("#")[0]
            src_gold[cid].add(src)

    from sentence_transformers import SentenceTransformer
    import numpy as np

    st = SentenceTransformer(EMBED, device=common.device())
    qv = st.encode([f'{c["title"]} {c["text"]}' for c in coms],
                   normalize_embeddings=True)
    pv = st.encode(texts, normalize_embeddings=True)
    sims = np.asarray(qv) @ np.asarray(pv).T

    report = {"embed": EMBED, "chunk": 2400, "candidates": K_CANDIDATES,
              "top_sources": TOP_SOURCES, "n_chunks": len(chunks),
              "device": common.device()}

    for ce_name, kind in RERANKERS.items():
        score_fn = _load_ce(ce_name, kind)
        t0 = time.time()
        ranked_chunks, ranked_srcs = {}, {}
        for qi, c in enumerate(coms):
            q = f'{c["title"]} {c["text"]}'
            top = list(np.argsort(-sims[qi])[:K_CANDIDATES])
            ce = score_fn(q, [texts[i] for i in top])
            order = [top[i] for i in
                     sorted(range(len(top)), key=lambda i: -ce[i])]
            # best chunk per source, rerank order preserved
            seen, sel = set(), []
            for i in order:
                if srcs[i] in seen:
                    continue
                seen.add(srcs[i])
                sel.append(i)
            sel = sel[:TOP_SOURCES]
            ranked_chunks[c["id"]] = [ids[i] for i in sel]
            ranked_srcs[c["id"]] = [srcs[i] for i in sel]
        ms = round((time.time() - t0) * 1000 / len(coms))

        rep = metrics.ranking_report(ranked_chunks, relevance,
                                     k_list=(1, 3, 5))
        # source-level recall/precision on the proposed sources
        rs, ps = [], []
        for c in coms:
            gold = src_gold[c["id"]]
            got = set(ranked_srcs[c["id"]])
            rs.append(len(gold & got) / len(gold) if gold else 0.0)
            ps.append(len(gold & got) / TOP_SOURCES)
        rep["src_recall@5"] = round(sum(rs) / len(rs), 4)
        rep["src_precision@5"] = round(sum(ps) / len(ps), 4)
        report[ce_name] = {**rep, "ms_per_commitment": ms}
        print(f"{ce_name}\n  chunk r@5={rep['recall@5']} "
              f"p@5={rep['precision@5']} ndcg={rep['ndcg@10']} "
              f"mrr={rep['mrr']} | src r@5={rep['src_recall@5']} "
              f"p@5={rep['src_precision@5']} ({ms}ms/commitment)")

    common.save_result("production_pipeline", report)


if __name__ == "__main__":
    main()
