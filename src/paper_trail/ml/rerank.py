"""Cross-encoder rerankers — stage 2 of evidence retrieval.

Same pattern as embeddings: a small interface, a local ONNX default
(fastembed, multilingual, no extra dependencies), an optional
sentence-transformers provider for the benchmarked bge-reranker-v2-m3,
and "none" to disable reranking entirely (embedding order is kept).

Selection: PAPER_TRAIL_RERANKER
    unset        -> BAAI/bge-reranker-v2-m3 (benchmarked best on the
                    production pipeline), falling back to the fastembed
                    jina multilingual reranker when sentence-transformers
                    is not installed
    "none"       -> no reranker
    a model name -> fastembed provider if supported there, else
                    sentence-transformers
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

import requests

log = logging.getLogger(__name__)

DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"
FALLBACK_RERANKER = "jinaai/jina-reranker-v2-base-multilingual"
JINA_RERANKER = "jina-reranker-v2-base-multilingual"


class Reranker(ABC):
    name: str

    @abstractmethod
    def score(self, query: str, passages: list[str]) -> list[float]:
        """One relevance score per passage — rank, don't threshold."""


class FastembedReranker(Reranker):
    """Local ONNX cross-encoder — multilingual, CPU-friendly, no torch."""

    def __init__(self, model: str = DEFAULT_RERANKER,
                 cache_dir: str | None = None):
        # keep HF's xet shared-blob store off: it scatters a model's
        # external ONNX data outside the model dir and onnxruntime
        # refuses to load it
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.name = model
        self._model = TextCrossEncoder(
            model_name=model, cache_dir=cache_dir,
            threads=os.cpu_count())

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, passages)]


class SentenceTransformerReranker(Reranker):
    """sentence-transformers cross-encoder — for the benchmarked
    BAAI/bge-reranker-v2-m3. Only usable when the `ml` extra is
    installed; the app never hard-requires it."""

    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder

        self.name = model
        self._model = CrossEncoder(model)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict(
            [[query, p] for p in passages])]


class JinaReranker(Reranker):
    """Hosted cross-encoder via the Jina AI rerank API — same task as the
    local ONNX reranker, no model download. Needs JINA_API_KEY."""

    def __init__(self, model: str = JINA_RERANKER,
                 api_key: str | None = None):
        key = api_key or os.environ.get("JINA_API_KEY")
        if not key:
            raise ValueError("JINA_API_KEY is not set")
        self.name = model
        self._headers = {"Authorization": f"Bearer {key}"}

    def score(self, query: str, passages: list[str]) -> list[float]:
        resp = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers=self._headers,
            json={"model": self.name, "query": query,
                  "documents": passages, "top_n": len(passages)},
            timeout=120,
        )
        resp.raise_for_status()
        scores = [0.0] * len(passages)
        for r in resp.json()["results"]:
            scores[r["index"]] = float(r["relevance_score"])
        return scores


_FASTEMBED_MODELS = {
    "Xenova/ms-marco-MiniLM-L-6-v2",
    "Xenova/ms-marco-MiniLM-L-12-v2",
    "BAAI/bge-reranker-base",
    "jinaai/jina-reranker-v1-tiny-en",
    "jinaai/jina-reranker-v1-turbo-en",
    "jinaai/jina-reranker-v2-base-multilingual",
}


def get_reranker(name: str | None = None,
                 cache_dir: str | None = None) -> Reranker | None:
    """Build the configured reranker; None means 'keep embedding order'."""
    name = name if name is not None else os.environ.get(
        "PAPER_TRAIL_RERANKER", DEFAULT_RERANKER)
    if name.lower() in ("none", "off", ""):
        return None
    if name == "jina" or name.startswith("jina-reranker"):
        return JinaReranker(name if name != "jina" else JINA_RERANKER)

    builds = ((FastembedReranker, SentenceTransformerReranker)
              if name in _FASTEMBED_MODELS
              else (SentenceTransformerReranker, FastembedReranker))
    for build in builds:
        try:
            return (build(name, cache_dir=cache_dir)
                        if build is FastembedReranker else build(name))
        except Exception:
            continue

    # configured model unavailable — degrade to the bundled ONNX reranker
    if name != FALLBACK_RERANKER:
        log.warning("reranker %s unavailable; falling back to %s",
                    name, FALLBACK_RERANKER)
        try:
            return FastembedReranker(FALLBACK_RERANKER, cache_dir=cache_dir)
        except Exception as exc:  # pragma: no cover - env dependent
            log.warning("fallback reranker unavailable (%s)", exc)
    return None
