"""Embedding providers.

One pretrained multilingual model is enough at this scale. The default is a
local ONNX runtime (fastembed); swapping in a hosted endpoint only means
implementing `embed()` against that service — nothing else changes.
"""

from __future__ import annotations

import hashlib
import os
import threading
from abc import ABC, abstractmethod

import numpy as np
import requests

# benchmarked stage-1 retriever, ~220MB onnx, e5-large is better but needs ~2GB
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
JINA_EMBED_MODEL = "jina-embeddings-v3"
OPENAI_EMBED_MODEL = "bge-m3"


class EmbeddingProvider(ABC):
    model_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text."""


class FastEmbedProvider(EmbeddingProvider):
    """Local multilingual embeddings via fastembed (ONNX, CPU-friendly)."""

    def __init__(self, model: str, cache_dir: str | None = None,
                 providers: list[str] | None = None):
        # lazy: TextEmbedding() pulls ~220MB, at construction it wedged every request on a 1GB tier
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
                        # 1 thread is too slow for doc batches, max spikes memory
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


class OpenAICompatEmbeddingProvider(EmbeddingProvider):
    """any openai-compatible /embeddings endpoint (llama.cpp, vllm, tei, ollama)

    model_name is prefixed so cached vectors never mix with another model's
    """

    def __init__(self, base_url: str, model: str = OPENAI_EMBED_MODEL,
                 api_key: str | None = None, batch_size: int = 16):
        if not base_url:
            raise ValueError("PAPER_TRAIL_EMBED_BASE_URL is not set")
        self.model_name = f"openai:{model}"
        self._model = model
        self._url = base_url.rstrip("/") + "/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key or 'local'}"}
        self._batch = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            resp = requests.post(
                self._url, headers=self._headers,
                json={"model": self._model, "input": batch}, timeout=120)
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            if [d["index"] for d in data] != list(range(len(batch))):
                raise ValueError(
                    f"embeddings: sent {len(batch)} texts, got indices "
                    f"{[d['index'] for d in data]}")
            out.extend(list(map(float, d["embedding"])) for d in data)
        return out


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
    a_, b_ = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(a_) * np.linalg.norm(b_)
    return float(a_ @ b_ / denom) if denom else 0.0


def get_provider(model: str | None = None,
                 cache_dir: str | None = None,
                 providers: list[str] | None = None,
                 base_url: str | None = None,
                 api_key: str | None = None) -> EmbeddingProvider:
    """fastembed locally by default, "jina" for the hosted api, "openai:<model>" or
    "bge-m3" for an openai-compatible endpoint (PAPER_TRAIL_EMBED_BASE_URL),
    hashing only when asked"""
    model = model or os.environ.get("PAPER_TRAIL_EMBED_MODEL")
    if model == "hashing":
        return HashingProvider()
    if model and (model.startswith("openai:") or model == "bge-m3"):
        return OpenAICompatEmbeddingProvider(
            base_url or os.environ.get("PAPER_TRAIL_EMBED_BASE_URL", ""),
            model.removeprefix("openai:"),
            api_key=api_key or os.environ.get("PAPER_TRAIL_EMBED_API_KEY"))
    if model == "jina" or (model or "").startswith("jina-embeddings"):
        return JinaEmbeddingProvider(
            model if model != "jina" else JINA_EMBED_MODEL)
    return FastEmbedProvider(model or DEFAULT_EMBED_MODEL,
                             cache_dir=cache_dir, providers=providers)
