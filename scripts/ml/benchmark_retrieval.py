"""compare baseline weighted fusion against RRF/reranking on labeled passages

uv run python scripts/ml/benchmark_retrieval.py corpus.json --model hashing
corpus: {"documents": [{"id": "d", "text": "..."}],
         "queries": [{"text": "...", "relevant": ["d"]}]}
use --model openai:BAAI/bge-m3 --base-url http://infinity:7997/v1
and --rerank-url to measure the real local stack; no model downloads by default
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from paper_trail.ml.embeddings import get_provider
from paper_trail.ml.nlp import HuSpacyAnalyzer
from paper_trail.ml.rerank import get_reranker
from paper_trail.ml.retrieval import reciprocal_rank_fusion
from paper_trail.repositories.indexing import _norm, lexical_scores, stemmer_for


def metrics(order, relevant, k):
    chosen = order[:k]
    return {"recall": len(set(chosen) & relevant) / len(relevant),
            "mrr": next((1 / rank for rank, key in enumerate(chosen, 1) if key in relevant), 0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--model", default="hashing")
    parser.add_argument("--baseline-model", default="hashing")
    parser.add_argument("--base-url")
    parser.add_argument("--rerank-url")
    parser.add_argument("--huspacy", dest="huspacy", action="store_true")
    parser.add_argument("--rerank-model", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--api-key")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("k must be positive")
    corpus = json.loads(args.corpus.read_text())
    texts = [d["text"] for d in corpus["documents"]]
    ids = [d["id"] for d in corpus["documents"]]
    if not texts or not corpus["queries"] or len(ids) != len(set(ids)):
        parser.error("corpus needs unique documents and labeled queries")
    baseline = get_provider(args.baseline_model, args.base_url, args.api_key)
    provider = get_provider(args.model, args.base_url, args.api_key)
    analyzer = HuSpacyAnalyzer() if args.huspacy else None
    reranker = get_reranker("goethe" if args.rerank_url else "none", args.rerank_url,
                            args.api_key, args.rerank_model, 20)
    started = time.monotonic()
    vectors = {"baseline": np.array(baseline.embed(texts)), "new": np.array(provider.embed(texts))}
    results = {name: [] for name in vectors}
    for row in corpus["queries"]:
        relevant = set(row["relevant"])
        if not relevant or not relevant.issubset(set(ids)):
            parser.error("every query needs nonempty known relevant ids")
        for name, embedder in [("baseline", baseline), ("new", provider)]:
            query = np.array(embedder.embed([row["text"]])[0])
            matrix = vectors[name]
            norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
            dense = matrix @ query / np.maximum(norms, 1e-12)
            lexical = lexical_scores(row["text"], texts, stemmer_for("hungarian"),
                                     analyzer if name == "new" else None)
            if name == "baseline":
                order = np.argsort(-(_norm(dense) + _norm(lexical)), kind="stable").tolist()
            else:
                rankings = [
                    np.argsort(-dense, kind="stable"),
                    [int(i) for i in np.argsort(-lexical, kind="stable") if lexical[i] > 0]]
                fused = reciprocal_rank_fusion(rankings)
                order = sorted(fused, key=lambda i: (-fused[i], i))[:20]
                if reranker:
                    scores = reranker.score(row["text"], [texts[i] for i in order])
                    order = [i for _, i in sorted(zip(scores, order, strict=True), reverse=True)]
            results[name].append(metrics([ids[i] for i in order], relevant, args.k))
    report = {name: {key + f"@{args.k}": sum(r[key] for r in rows) / len(rows)
                     for key in ["recall", "mrr"]} for name, rows in results.items()}
    report.update({"queries": len(corpus["queries"]), "model": args.model,
                   "baseline_model": args.baseline_model,
                   "elapsed_seconds": time.monotonic() - started,
                   "corpus": str(args.corpus)})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
