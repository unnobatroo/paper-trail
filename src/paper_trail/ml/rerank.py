"""cross-encoder rerankers, stage 2 of retrieval

PAPER_TRAIL_RERANKER:
    unset/"auto"  jina if JINA_API_KEY is set, else none
    "none"        keep embedding order
    "jina"        hosted jina (falls back to none without a key)
    <model name>  fastembed if it supports it, else sentence-transformers
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
        """one score per passage, rank it, don't threshold it"""


class FastembedReranker(Reranker):
    """local onnx cross-encoder, multilingual, cpu, no torch"""

    def __init__(self, model: str = DEFAULT_RERANKER,
                 cache_dir: str | None = None):
        # hf xet store scatters onnx data outside the model dir and onnxruntime refuses to load it
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.name = model
        self._model = TextCrossEncoder(
            model_name=model, cache_dir=cache_dir,
            threads=os.cpu_count())

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, passages)]


class SentenceTransformerReranker(Reranker):
    """sentence-transformers cross-encoder (bge-reranker-v2-m3), needs the `ml` extra"""

    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder

        self.name = model
        self._model = CrossEncoder(model)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict(
            [[query, p] for p in passages])]


class JinaReranker(Reranker):
    """jina rerank api, no model download, needs JINA_API_KEY"""

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
    """build the configured reranker, None = keep embedding order"""
    name = name if name is not None else os.environ.get(
        "PAPER_TRAIL_RERANKER", "")
    lowered = name.lower()
    if lowered in ("none", "off"):
        return None
    if lowered in ("", "auto"):
        if os.environ.get("JINA_API_KEY"):
            return JinaReranker()
        log.info("no reranker configured — set JINA_API_KEY for the "
                 "hosted one, or PAPER_TRAIL_RERANKER for a local model")
        return None
    if name == "jina" or name.startswith("jina-reranker"):
        try:
            return JinaReranker(name if name != "jina" else JINA_RERANKER)
        except ValueError as exc:
            log.warning("%s — reranking disabled", exc)
            return None

    builds = ((FastembedReranker, SentenceTransformerReranker)
              if name in _FASTEMBED_MODELS
              else (SentenceTransformerReranker, FastembedReranker))
    for build in builds:
        try:
            return (build(name, cache_dir=cache_dir)
                    if build is FastembedReranker else build(name))
        except Exception:
            continue

    # model unavailable, fall back to the bundled onnx reranker
    if name != FALLBACK_RERANKER:
        log.warning("reranker %s unavailable; falling back to %s",
                    name, FALLBACK_RERANKER)
        try:
            return FastembedReranker(FALLBACK_RERANKER, cache_dir=cache_dir)
        except Exception as exc:  # pragma: no cover - env dependent
            log.warning("fallback reranker unavailable (%s)", exc)
    return None
