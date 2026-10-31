"""evidence retrieval benchmark: commitment -> ranked passages, through the real postgres index

  DATABASE_URL=<scratch db> MODEL_CA_BUNDLE=... uv run python scripts/ml/benchmark_retrieval.py \\
    corpus.json --qrels qrels.jsonl --model openai:Qwen/Qwen3-Embedding-0.6B \\
    --base-url https://goethe:8443/v1 --rerank-url https://goethe:8443/v1 --pool pool.jsonl

corpus: {"documents": [{"id": "d", "text": "...", "title": "..."}],
         "queries": [{"id": "q", "text": "...", "relevant": ["d"]}]}
qrels jsonl, one judgment per line, later files win: {"query": "q", "doc": "d", "grade": 0-3}
  0 unrelated, 1 related but indirect, 2 supporting, 3 direct implementation

systems: dense (cosine), hybrid (dense + lexical rrf, what prod retrieves with), rerank
(hybrid top --rerank-k re-scored by the cross-encoder, what prod shows). one chunk per doc
under bench:// urls, so point it at a scratch database. --pool writes the unjudged pairs
any system put in its top --pool-depth, that's the next labeling batch
"""
import argparse
import json
import math
import os
import time
from pathlib import Path

from paper_trail.ml.embeddings import get_provider
from paper_trail.ml.rerank import get_reranker
from paper_trail.repositories.index import PostgresPageStore, PostgresVectorIndex
from paper_trail.sources.fetch import FetchedPage

CHUNK = 2400  # same as evidence_service, part of the cache key only


def load_qrels(corpus: dict, paths: list[Path]) -> dict[str, dict[str, int]]:
    """query -> doc -> grade. inline "relevant" lists count as grade 1, files override"""
    qrels: dict[str, dict[str, int]] = {}
    for q in corpus["queries"]:
        rel = q.get("relevant", [])
        qrels[q["id"]] = dict(rel) if isinstance(rel, dict) else dict.fromkeys(rel, 1)
    for path in paths:
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                qrels.setdefault(row["query"], {})[row["doc"]] = int(row["grade"])
    return qrels


def metrics(order: list[str], grades: dict[str, int], k: int, min_grade: int = 1) -> dict:
    """graded ndcg, binary recall/mrr/p@1 (grade >= min_grade counts), judged = labeled share
    of top k"""
    top = order[:k]
    relevant = {d for d, g in grades.items() if g >= min_grade}
    dcg = sum((2 ** grades.get(d, 0) - 1) / math.log2(i + 2) for i, d in enumerate(top))
    ideal = sorted((g for g in grades.values() if g > 0), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return {"recall": len(set(top) & relevant) / len(relevant) if relevant else 0.0,
            "mrr": next((1 / r for r, d in enumerate(top, 1) if d in relevant), 0.0),
            "ndcg": dcg / idcg if idcg else 0.0,
            "p@1": float(bool(top) and top[0] in relevant),
            "judged": sum(d in grades for d in top) / len(top) if top else 0.0}


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """chance a relevant pair outscores an unrelated one: can a threshold say 'no evidence'"""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def _cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def rank(dsn: str, corpus: dict, embedder, model: str, reranker=None, instruct: str = "",
         rerank_k: int = 20, analyzer=None, ts_config: str = "simple",
         ) -> dict[str, dict[str, list[tuple[str, float]]]]:
    """system -> query id -> [(doc id, score)] best first"""
    pages = [FetchedPage(f"bench://{d['id']}", d["id"], d["text"]) for d in corpus["documents"]]
    store = PostgresPageStore(dsn)
    index = PostgresVectorIndex(dsn, ts_config=ts_config, analyzer=analyzer)
    vectors = {}
    for page in pages:
        cached = index.get(page, model, CHUNK)
        if cached is None:
            store.put(page)
            cached = [(page.text, embedder.embed([page.text])[0])]
            index.put(page, model, CHUNK, cached)
        vectors[page.title] = cached[0][1]
    out: dict[str, dict] = {"dense": {}, "hybrid": {}}
    if reranker:
        out["rerank"] = {}
    texts = {d["id"]: d["text"] for d in corpus["documents"]}
    for q in corpus["queries"]:
        qvec = embedder.embed([instruct + q["text"]])[0]
        out["dense"][q["id"]] = sorted(((d, _cosine(qvec, v)) for d, v in vectors.items()),
                                       key=lambda r: -r[1])
        hits = index.match(qvec, q["text"], model, CHUNK, pages, len(pages))
        hybrid = [(page.title, 1 / r) for r, (page, _, _) in enumerate(hits, 1)]
        out["hybrid"][q["id"]] = hybrid
        if reranker:
            head = hybrid[:rerank_k]
            scores = reranker.score(q["text"], [texts[d] for d, _ in head]) if head else []
            out["rerank"][q["id"]] = sorted(zip([d for d, _ in head], scores, strict=True),
                                            key=lambda r: -r[1]) + hybrid[rerank_k:]
    return out


def report(ranked: dict, qrels: dict[str, dict[str, int]], ks: tuple[int, ...],
           min_grade: int = 1) -> dict:
    """mean metrics over queries with something relevant, plus score separation"""
    answered = [q for q, g in qrels.items() if any(v >= min_grade for v in g.values())]
    result = {}
    for system, per_query in ranked.items():
        row: dict = {}
        for k in ks:
            rows = [metrics([d for d, _ in per_query[q]], qrels[q], k, min_grade)
                    for q in answered if q in per_query]
            for name in ("recall", "mrr", "ndcg", "p@1", "judged"):
                if rows and (name != "p@1" or k == ks[0]):
                    key = name if name == "p@1" else f"{name}@{k}"
                    row[key] = round(sum(r[name] for r in rows) / len(rows), 3)
        if system != "hybrid":  # hybrid scores are ranks, not comparable across queries
            pos, neg = [], []
            for q, scores in per_query.items():
                for d, s in scores:
                    grade = qrels.get(q, {}).get(d)
                    if grade is not None:
                        (pos if grade >= min_grade else neg).append(s)
            score = auroc(pos, neg)
            row["auroc"] = None if score is None else round(score, 3)
        result[system] = row
    return result


def pool(ranked: dict, qrels: dict[str, dict[str, int]], depth: int) -> list[dict]:
    """unjudged (query, doc) pairs in any system's top depth, deduped"""
    seen = set()
    for per_query in ranked.values():
        for q, scores in per_query.items():
            for d, _ in scores[:depth]:
                if d not in qrels.get(q, {}):
                    seen.add((q, d))
    return [{"query": q, "doc": d} for q, d in sorted(seen)]


def run(dsn: str, corpus: dict, embedder, model: str, k: int, analyzer=None,
        reranker=None) -> dict:
    """the hybrid (or reranked) recall/mrr at k, kept small for tests"""
    for i, q in enumerate(corpus["queries"]):
        q.setdefault("id", str(i))
    ranked = rank(dsn, corpus, embedder, model, reranker, analyzer=analyzer)
    system = "rerank" if reranker else "hybrid"
    return {key: value for key, value in
            report({system: ranked[system]}, load_qrels(corpus, []), (k,))[system].items()
            if key in (f"recall@{k}", f"mrr@{k}")}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--qrels", type=Path, action="append", default=[])
    parser.add_argument("--model", default="hashing")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key", default=os.environ.get("MODEL_API_KEY"))
    parser.add_argument("--rerank-url")
    parser.add_argument("--rerank-model", default="BAAI/bge-reranker-v2-m3")
    parser.add_argument("--rerank-k", type=int, default=20)
    parser.add_argument("--instruct", default="",
                        help="query prefix, qwen3-embedding wants 'Instruct: ...\\nQuery: '")
    parser.add_argument("--huspacy", action="store_true", help="lemmatize the lexical side")
    parser.add_argument("--ts-config", default="hungarian", help="lexical stemmer, prod: hungarian")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20])
    parser.add_argument("--min-grade", type=int, default=1,
                        help="lowest grade that counts as found evidence, 2 = skip indirect")
    parser.add_argument("--pool", type=Path, help="write unjudged top pairs here")
    parser.add_argument("--pool-depth", type=int, default=10)
    parser.add_argument("--runs", type=Path, help="write the full rankings here")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text())
    for i, q in enumerate(corpus["queries"]):
        q.setdefault("id", str(i))
    ids = [d["id"] for d in corpus["documents"]]
    if min(args.k) < 1 or not ids or len(ids) != len(set(ids)) or not corpus["queries"]:
        parser.error("needs k >= 1, unique document ids and some queries")
    qrels = load_qrels(corpus, args.qrels)
    if not {d for g in qrels.values() for d in g} <= set(ids):
        parser.error("qrels name documents the corpus doesn't have")
    analyzer = None
    if args.huspacy:
        from paper_trail.ml.nlp import HuSpacyAnalyzer
        analyzer = HuSpacyAnalyzer()
    reranker = get_reranker("goethe" if args.rerank_url else "none", args.rerank_url,
                            args.api_key, args.rerank_model, 20)
    started = time.monotonic()
    ranked = rank(os.environ["DATABASE_URL"], corpus,
                  get_provider(args.model, args.base_url, args.api_key), args.model, reranker,
                  args.instruct.replace("\\n", "\n"), args.rerank_k, analyzer, args.ts_config)
    answered = sum(any(g >= args.min_grade for g in v.values()) for v in qrels.values())
    print(json.dumps({
        "systems": report(ranked, qrels, tuple(sorted(args.k)), args.min_grade),
        "min_grade": args.min_grade,
        "queries": len(corpus["queries"]), "with_relevant": answered,
        "judgments": sum(map(len, qrels.values())), "model": args.model,
        "instruct": bool(args.instruct), "huspacy": args.huspacy,
        "corpus": str(args.corpus), "qrels": [str(p) for p in args.qrels],
        "elapsed_seconds": round(time.monotonic() - started, 1)}, indent=2))
    if args.pool:
        rows = pool(ranked, qrels, args.pool_depth)
        args.pool.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    if args.runs:
        args.runs.write_text(json.dumps(ranked, ensure_ascii=False))


if __name__ == "__main__":
    main()
