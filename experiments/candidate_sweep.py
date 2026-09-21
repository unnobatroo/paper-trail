"""Candidate-count sweep — how wide must stage-1 reach?

For k in {5,10,20,40}: take the top-k stage-1 candidates per commitment,
rerank them with the cross-encoder, measure final ranking metrics and
wall-clock latency. Also reports the stage-1 recall ceiling at each k —
what reranking can possibly recover.

Split=both: metrics over all sources, and over test sources only (the
fine-tuned checkpoint is only ever judged on test — it trained on train).

Usage:
    uv run --group ml python experiments/candidate_sweep.py
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from collections import defaultdict

sys.path.insert(0, ".")
from experiments import common, corpus, data, metrics  # noqa: E402

EMBED = "intfloat/multilingual-e5-large-instruct"
CE_BASE = "BAAI/bge-reranker-v2-m3"
CE_FT = "experiments/checkpoints/reranker_ft"
KS = (5, 10, 20, 40)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="fixed_2400")
    args = ap.parse_args()

    chunks, relevance = corpus.load(args.corpus)
    coms = data.commitments()
    ids = [c["id"] for c in chunks]
    texts = [c["text"] for c in chunks]

    from sentence_transformers import SentenceTransformer, CrossEncoder
    import numpy as np

    st = SentenceTransformer(EMBED, device=common.device())
    qv = st.encode([f'{c["title"]} {c["text"]}' for c in coms],
                   normalize_embeddings=True)
    pv = st.encode(texts, normalize_embeddings=True)
    sims = np.asarray(qv) @ np.asarray(pv).T

    rankers = {"ce_pretrained": CE_BASE}
    if pathlib.Path(CE_FT).exists():
        rankers["ce_finetuned"] = CE_FT

    # CE scores are k-independent — score every pair once per ranker.
    ce_scores = {}
    for rname, path in rankers.items():
        ce = CrossEncoder(path, device=common.device())
        t0 = time.time()
        per_c = {}
        for qi, c in enumerate(coms):
            per_c[c["id"]] = [float(s) for s in ce.predict(
                [[f'{c["title"]} {c["text"]}', t] for t in texts])]
        ce_scores[rname] = {"per_c": per_c,
                            "ms_per_commitment":
                                round((time.time() - t0) * 1000 / len(coms))}
        print(f"{rname}: scored {len(chunks)} chunks x {len(coms)} "
              f"commitments in {round(time.time() - t0, 1)}s")

    # restrict labels per split for held-out reporting
    rel_all = relevance
    rel_test = {k: v for k, v in relevance.items()
                if data.split_of(k[1].split("#")[0]) == "test"}

    report = {"corpus": args.corpus, "embed": EMBED}
    for k in KS:
        kk = min(k, len(chunks))
        ceiling = []
        topk = {}
        for qi, c in enumerate(coms):
            top = list(np.argsort(-sims[qi])[:kk])
            topk[c["id"]] = top
            gold = {p for (cid, p), r in rel_all.items()
                    if cid == c["id"] and r >= 1}
            ceiling.append(
                len(gold & {ids[i] for i in top}) / len(gold)
                if gold else 0.0)
        stage1 = round(sum(ceiling) / len(ceiling), 4)

        row = {"stage1_recall_ceiling": stage1}
        for rname in rankers:
            scores_map = ce_scores[rname]["per_c"]
            ranked = {}
            for c in coms:
                idxs = topk[c["id"]]
                order = sorted(idxs,
                               key=lambda i: -scores_map[c["id"]][i])
                ranked[c["id"]] = [ids[i] for i in order]
            rep_all = metrics.ranking_report(ranked, rel_all,
                                             k_list=(1, 3, 5))
            rep_test = metrics.ranking_report(ranked, rel_test,
                                              k_list=(1, 3, 5))
            row[rname] = {"all": rep_all, "test": rep_test,
                          "rerank_ms_per_commitment":
                              ce_scores[rname]["ms_per_commitment"]}
            print(f"k={kk:2d} ceiling={stage1:.3f} {rname:14s} "
                  f"all: r@5={rep_all['recall@5']:.3f} "
                  f"ndcg={rep_all['ndcg@10']:.3f} "
                  f"mrr={rep_all['mrr']:.3f} | "
                  f"test: r@5={rep_test['recall@5']:.3f} "
                  f"ndcg={rep_test['ndcg@10']:.3f}")
        report[f"k={kk}"] = row

    common.save_result("candidate_sweep", report)


if __name__ == "__main__":
    main()
