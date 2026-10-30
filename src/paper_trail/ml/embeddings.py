"""embedders: local fastembed for offline dev, an openai-style server for real, hashing for tests"""

from __future__ import annotations

import hashlib
import os
import threading
from abc import ABC, abstractmethod

import numpy as np

from .client import model_client

# ~220mb onnx, fine on cpu
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingProvider(ABC):
    model_name: str  # cache key, vectors from different models never mix

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder(EmbeddingProvider):
    def __init__(self, model: str = DEFAULT_EMBED_MODEL, cache_dir: str | None = None):
        self.model_name, self._cache_dir = model, cache_dir
        self._model = None
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        # lazy, loading at boot froze small boxes
        with self._lock:
            if self._model is None:
                os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=self._cache_dir,
                                            threads=min(4, os.cpu_count() or 1))
        return [list(map(float, v)) for v in self._model.embed(texts)]


class HttpEmbedder(EmbeddingProvider):
    def __init__(self, client, model: str, batch_size: int = 16):
        self.model_name = f"openai:{model}"
        self._client, self._model, self._batch = client, model, batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            # float, the sdk asks for base64 by default and not every server does it
            resp = self._client.embeddings.create(model=self._model, input=batch,
                                                  encoding_format="float")
            rows = sorted(resp.data, key=lambda r: r.index)
            if [r.index for r in rows] != list(range(len(batch))):
                raise ValueError(f"sent {len(batch)} texts, got indices {[r.index for r in rows]}")
            out += [list(map(float, r.embedding)) for r in rows]
        return out


class HashingProvider(EmbeddingProvider):
    """token-hash vectors for tests, meaningless but the pipeline runs"""

    DIM = 384
    model_name = "hashing"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.DIM
            for token in text.lower().split():
                vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % self.DIM] += 1.0
            out.append(vec)
        return out


def cosine(a: list[float], b: list[float]) -> float:
    a_, b_ = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(a_) * np.linalg.norm(b_)
    return float(a_ @ b_ / denom) if denom else 0.0


def get_provider(model: str, base_url: str | None = None, api_key: str | None = None,
                 cache_dir: str | None = None) -> EmbeddingProvider:
    """"openai:<model>" -> server, "hashing" -> stub, anything else -> local fastembed"""
    if model == "hashing":
        return HashingProvider()
    if model.startswith("openai:"):
        return HttpEmbedder(model_client(base_url, api_key), model.removeprefix("openai:"))
    return LocalEmbedder(model or DEFAULT_EMBED_MODEL, cache_dir)
