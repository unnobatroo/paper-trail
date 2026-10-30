"""retrieval benchmark goes through the real index"""
import importlib.util
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
    report = bench.run(dsn, CORPUS, HashingProvider(), "hashing", k=1)
    assert report == {"recall@1": 1.0, "mrr@1": 1.0}


def test_metrics():
    assert bench.metrics(["a", "b", "c"], {"b", "x"}, 2) == {"recall": 0.5, "mrr": 0.5}
