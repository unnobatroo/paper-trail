"""recall/mrr on labeled passages through the real postgres hybrid index (+ optional rerank)

  DATABASE_URL=<scratch db> uv run python scripts/ml/benchmark_retrieval.py corpus.json \\
    --model openai:Qwen/Qwen3-Embedding-0.6B --base-url https://goethe:8443/v1 --rerank-url ...
corpus: {"documents": [{"id": "d", "text": "..."}],
         "queries": [{"text": "...", "relevant": ["d"]}]}

one chunk per document, written under bench:// urls into pages/chunks, so point it at a
scratch database. --baseline-model runs the same thing with another embedder to compare
"""
import argparse
import json
import os
import time
from pathlib import Path

from paper_trail.ml.embeddings import get_provider
from paper_trail.ml.rerank import get_reranker
from paper_trail.repositories.postgres.index import PostgresPageStore, PostgresVectorIndex
from paper_trail.sources.fetch import FetchedPage

CHUNK = 2400  # same as evidence_service, part of the cache key only


def metrics(order: list[str], relevant: set[str], k: int) -> dict:
    chosen = order[:k]
    return {"recall": len(set(chosen) & relevant) / len(relevant),
            "mrr": next((1 / rank for rank, key in enumerate(chosen, 1) if key in relevant), 0)}


def run(dsn: str, corpus: dict, embedder, model: str, k: int, analyzer=None,
        reranker=None) -> dict:
    pages = [FetchedPage(f"bench://{d['id']}", d["id"], d["text"]) for d in corpus["documents"]]
    store, index = PostgresPageStore(dsn), PostgresVectorIndex(dsn, analyzer=analyzer)
    for page, vec in zip(pages, embedder.embed([p.text for p in pages]), strict=True):
        store.put(page)
        index.put(page, model, CHUNK, [(page.text, vec)])
    rows = []
    for q in corpus["queries"]:
        hits = index.match(embedder.embed([q["text"]])[0], q["text"], model, CHUNK, pages, 20)
        if reranker and hits:
            scores = reranker.score(q["text"], [text for _, text, _ in hits])
            hits = [h for _, h in sorted(zip(scores, hits, strict=True), key=lambda p: -p[0])]
        rows.append(metrics([page.title for page, _, _ in hits], set(q["relevant"]), k))
    return {f"{m}@{k}": sum(r[m] for r in rows) / len(rows) for m in ("recall", "mrr")}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--model", default="hashing")
    parser.add_argument("--baseline-model", default="hashing")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--rerank-url")
    parser.add_argument("--rerank-model", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--huspacy", action="store_true", help="lemmatize the lexical side")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text())
    ids = [d["id"] for d in corpus["documents"]]
    if args.k < 1 or not ids or len(ids) != len(set(ids)) or not corpus["queries"] or any(
            not q["relevant"] or not set(q["relevant"]) <= set(ids) for q in corpus["queries"]):
        parser.error("needs k >= 1, unique document ids, queries with known relevant ids")
    dsn = os.environ["DATABASE_URL"]
    analyzer = None
    if args.huspacy:
        from paper_trail.ml.nlp import HuSpacyAnalyzer
        analyzer = HuSpacyAnalyzer()
    reranker = get_reranker("goethe" if args.rerank_url else "none", args.rerank_url,
                            args.api_key, args.rerank_model, 20)
    started = time.monotonic()
    report = {
        "baseline": run(dsn, corpus, get_provider(args.baseline_model, args.base_url,
                                                  args.api_key), args.baseline_model, args.k),
        "new": run(dsn, corpus, get_provider(args.model, args.base_url, args.api_key),
                   args.model, args.k, analyzer, reranker),
        "queries": len(corpus["queries"]), "model": args.model,
        "baseline_model": args.baseline_model, "corpus": str(args.corpus),
        "elapsed_seconds": round(time.monotonic() - started, 1)}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
