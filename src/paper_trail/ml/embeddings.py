"""Embedding providers.

One pretrained multilingual model is enough at this scale. The default is a
local ONNX runtime (fastembed); swapping in a hosted endpoint only means
implementing `embed()` against that service — nothing else changes.
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
from abc import ABC, abstractmethod

import requests


# Benchmarked stage-1 retriever (see experiments/), ~220MB ONNX —
# small enough for free-tier hosts; e5-large is stronger but needs ~2GB.
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
JINA_EMBED_MODEL = "jina-embeddings-v3"


class EmbeddingProvider(ABC):
    model_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text."""


class FastEmbedProvider(EmbeddingProvider):
    """Local multilingual embeddings via fastembed (ONNX, CPU-friendly)."""

    def __init__(self, model: str, cache_dir: str | None = None,
                 providers: list[str] | None = None):
        # Lazy: TextEmbedding() downloads ~220MB and loads ONNX — too heavy
        # to run at service-construction time on a 1GB free tier (it wedged
        # every request). Load on first embed(), inside the worker thread.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        self.model_name = model
        self._cache_dir = cache_dir
        self._providers = providers or ["CPUExecutionProvider"]
        self._model = None
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding
                    self._model = TextEmbedding(
                        model_name=self.model_name,
                        cache_dir=self._cache_dir,
                        # e5-large on one core is far too slow for document
                        # batches, but max threads spikes memory — 4 is the
                        # safe middle
                        threads=min(4, os.cpu_count() or 1),
                        providers=self._providers,
                    )
        return [list(map(float, v)) for v in self._model.embed(texts)]


class SentenceTransformerProvider(EmbeddingProvider):
    """sentence-transformers embeddings — the proven path on GPU boxes
    where torch is already installed. Uses CUDA automatically."""

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model
        self._model = SentenceTransformer(model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True)]


class JinaEmbeddingProvider(EmbeddingProvider):
    """Hosted multilingual embeddings via the Jina AI API — no model
    download, no local compute. Needs JINA_API_KEY."""

    def __init__(self, model: str = JINA_EMBED_MODEL,
                 api_key: str | None = None):
        key = api_key or os.environ.get("JINA_API_KEY")
        if not key:
            raise ValueError("JINA_API_KEY is not set")
        self.model_name = model
        self._headers = {"Authorization": f"Bearer {key}"}

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers=self._headers,
            json={"model": self.model_name, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [list(map(float, d["embedding"])) for d in data]


class HashingProvider(EmbeddingProvider):
    """Deterministic token-hash vectors. For tests and fully offline runs —
    not semantically meaningful, but keeps the pipeline exercisable."""

    DIM = 384
    model_name = "hashing"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.DIM
            for token in text.lower().split():
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % self.DIM] += 1.0
            vectors.append(vec)
        return vectors


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def get_provider(model: str | None = None,
                 cache_dir: str | None = None,
                 providers: list[str] | None = None) -> EmbeddingProvider:
    """Default provider: fastembed locally; "jina" for the hosted Jina API;
    hashing only when explicitly asked."""
    model = model or os.environ.get("PAPER_TRAIL_EMBED_MODEL")
    if model == "hashing":
        return HashingProvider()
    if model == "jina" or (model or "").startswith("jina-embeddings"):
        return JinaEmbeddingProvider(
            model if model != "jina" else JINA_EMBED_MODEL)
    return FastEmbedProvider(model or DEFAULT_EMBED_MODEL,
                             cache_dir=cache_dir, providers=providers)
