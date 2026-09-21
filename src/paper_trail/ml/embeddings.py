"""Embedding providers.

One pretrained multilingual model is enough at this scale. The default is a
local ONNX runtime (fastembed); swapping in a hosted endpoint only means
implementing `embed()` against that service — nothing else changes.
"""

from __future__ import annotations

import hashlib
import math
import os
from abc import ABC, abstractmethod


DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-large"


class EmbeddingProvider(ABC):
    model_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text."""


class FastEmbedProvider(EmbeddingProvider):
    """Local multilingual embeddings via fastembed (ONNX, CPU-friendly)."""

    def __init__(self, model: str, cache_dir: str | None = None,
                 providers: list[str] | None = None):
        # hf_xet's shared blob store places a model's external ONNX data in
        # a different directory than the .onnx file — onnxruntime rejects it.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from fastembed import TextEmbedding

        self.model_name = model
        self._model = TextEmbedding(
            model_name=model, cache_dir=cache_dir,
            # e5-large on one core is far too slow for document batches,
            # but max threads spikes memory — 4 is the safe middle
            threads=min(4, os.cpu_count() or 1),
            providers=providers or ["CPUExecutionProvider"],
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
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
    """Default provider: fastembed locally; hashing only when explicitly asked."""
    model = model or os.environ.get("PAPER_TRAIL_EMBED_MODEL")
    if model == "hashing":
        return HashingProvider()
    return FastEmbedProvider(model or DEFAULT_EMBED_MODEL,
                             cache_dir=cache_dir, providers=providers)
