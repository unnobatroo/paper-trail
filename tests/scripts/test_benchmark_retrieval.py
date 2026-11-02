"""retrieval benchmark goes through the real index"""
import importlib.util
import json
from pathlib import Path

from paper_trail.ml.embeddings import HashingProvider

_spec = importlib.util.spec_from_file_location(
    "benchmark_retrieval",
    Path(__file__).resolve().parents[2] / "scripts" / "ml" / "benchmark_retrieval.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

CORPUS = {"documents": [{"id": "trees", "text": "fák ültetése a Bérkocsis utcában"},
                        {"id": "heat", "text": "távhő hőközpontok korszerűsítése"},
                        {"id": "bikes", "text": "kerékpártámaszok a tereken"}],
          "queries": [{"text": "fák ültetése", "relevant": ["trees"]},
                      {"text": "távhő korszerűsítése", "relevant": ["heat"]}]}


def test_easy_corpus_scores_perfectly(dsn):
    report = bench.run(dsn, json.loads(json.dumps(CORPUS)), HashingProvider(), "hashing", k=1)
    assert report == {"recall@1": 1.0, "mrr@1": 1.0}


def test_rank_gives_every_system_a_full_ranking(dsn):
    corpus = json.loads(json.dumps(CORPUS))
    for i, q in enumerate(corpus["queries"]):
        q["id"] = f"q{i}"
    ranked = bench.rank(dsn, corpus, HashingProvider(), "hashing")
    assert set(ranked) == {"dense", "hybrid"}
    assert ranked["dense"]["q0"][0][0] == "trees"
    assert len(ranked["dense"]["q1"]) == 3


def test_metrics_graded():
    m = bench.metrics(["a", "b", "c"], {"b": 3, "x": 1, "c": 0}, 2)
    assert m["recall"] == 0.5 and m["mrr"] == 0.5 and m["p@1"] == 0.0
    assert m["judged"] == 0.5
    assert 0 < m["ndcg"] < 1
    assert bench.metrics(["b", "x"], {"b": 3, "x": 1}, 2)["ndcg"] == 1.0


def test_auroc():
    assert bench.auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert bench.auroc([0.5], [0.5]) == 0.5
    assert bench.auroc([0.5], []) is None


def test_qrels_files_override_inline(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text('{"query": "0", "doc": "trees", "grade": 0}\n'
                    '{"query": "0", "doc": "bikes", "grade": 2}\n')
    corpus = json.loads(json.dumps(CORPUS))
    for i, q in enumerate(corpus["queries"]):
        q["id"] = str(i)
    assert bench.load_qrels(corpus, [path])["0"] == {"trees": 0, "bikes": 2}


def test_pool_is_unjudged_top_pairs():
    ranked = {"dense": {"q": [("a", 1), ("b", 0.5), ("c", 0.1)]},
              "rerank": {"q": [("c", 9), ("a", 1)]}}
    assert bench.pool(ranked, {"q": {"a": 2}}, 2) == [{"query": "q", "doc": "b"},
                                                      {"query": "q", "doc": "c"}]


def test_min_grade_drops_indirect():
    m = bench.metrics(["a", "b"], {"a": 1, "b": 2}, 1, min_grade=2)
    assert m["recall"] == 0.0 and m["mrr"] == 0.0
