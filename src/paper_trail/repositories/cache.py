"""System caches behind small interfaces — fetched pages and chunk vectors.

Two backends, same interface:

* file-backed (`FilePageStore`, `FileVectorIndex`) — the original
  `data/processed/fetched/` layout, used for SQLite/offline runs and tests;
* Postgres-backed (`SupabasePageStore`, `SupabaseVectorIndex` in
  `supabase_index.py`) — `pages`/`chunks` tables + pgvector, used when
  `SUPABASE_URL`/`SUPABASE_KEY` are configured.

Either way the invariant holds: a page is fetched once and embedded once
per model, then reused by every later evidence search.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from ..ml.embeddings import cosine
from ..sources.fetch import FetchedPage

# pgvector column width — every provider's vectors are right-padded to
# this length before storing. Zero-padding is cosine-neutral.
VECTOR_DIM = 1024


def pad_vector(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    """Right-pad with zeros to `dim`; longer vectors are left as-is."""
    if len(vec) >= dim:
        return vec
    return vec + [0.0] * (dim - len(vec))


def url_key(url: str) -> str:
    """Stable short key for a source URL — the file cache layout."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def content_key(model: str, chunk_size: int, text: str) -> str:
    """Content-addressed key for a document's chunk vectors: change the
    model, the chunk size or the text and the vectors are recomputed."""
    return hashlib.sha256(
        f"{model}|{chunk_size}|{text}".encode()).hexdigest()[:24]


class PageStore(ABC):
    """Fetch cache: URL → extracted page. fetch-once, read-forever."""

    @abstractmethod
    def get(self, url: str) -> FetchedPage | None:
        """The cached page, or None when it was never fetched."""

    @abstractmethod
    def put(self, page: FetchedPage) -> None:
        """Store a fetched page; re-putting the same URL is a no-op or
        an upsert — callers always treat the store as the source of truth."""

    def page_id(self, url: str) -> int | None:
        """Stable row id for chunk storage; file-backed stores have none."""
        return None


class VectorIndex(ABC):
    """Chunk embeddings for fetched pages + top-k cosine retrieval."""

    @abstractmethod
    def has(self, page: FetchedPage, model: str, chunk_size: int) -> bool:
        """Cheap existence check — never downloads vectors."""

    @abstractmethod
    def get(self, page: FetchedPage, model: str,
            chunk_size: int) -> list[tuple[str, list[float]]] | None:
        """Cached (chunk_text, vector) pairs for this page+model, or None."""

    @abstractmethod
    def put(self, page: FetchedPage, model: str, chunk_size: int,
            pairs: list[tuple[str, list[float]]]) -> None:
        """Persist chunk vectors for a page under the given model."""

    @abstractmethod
    def match(self, query: list[float], model: str, chunk_size: int,
              pages: list[FetchedPage],
              k: int) -> list[tuple[FetchedPage, str, float]]:
        """Top-k (page, chunk_text, cosine_similarity) across `pages`,
        ordered best-first. Pages without cached vectors are skipped."""


class FilePageStore(PageStore):
    """`<cache>/<url_hash>.txt` + `<url_hash>.json` — the original layout."""

    def __init__(self, cache_dir: Path):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, url: str) -> FetchedPage | None:
        txt = self._dir / f"{url_key(url)}.txt"
        meta = self._dir / f"{url_key(url)}.json"
        if not (txt.exists() and meta.exists()):
            return None
        m = json.loads(meta.read_text(encoding="utf-8"))
        return FetchedPage(
            url=url, title=m["title"],
            text=txt.read_text(encoding="utf-8"),
            published_on=date.fromisoformat(m["date"]) if m["date"] else None,
        )

    def put(self, page: FetchedPage) -> None:
        (self._dir / f"{url_key(page.url)}.txt").write_text(
            page.text, encoding="utf-8")
        (self._dir / f"{url_key(page.url)}.json").write_text(json.dumps({
            "title": page.title,
            "date": page.published_on.isoformat() if page.published_on else None,
        }), encoding="utf-8")


class FileVectorIndex(VectorIndex):
    """`<cache>/embeddings/<content_hash>.json` — chunks + vectors."""

    def __init__(self, cache_dir: Path):
        self._dir = Path(cache_dir) / "embeddings"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _file(self, page: FetchedPage, model: str,
              chunk_size: int) -> Path:
        return self._dir / f"{content_key(model, chunk_size, page.text)}.json"

    def has(self, page: FetchedPage, model: str, chunk_size: int) -> bool:
        return self._file(page, model, chunk_size).exists()

    def get(self, page: FetchedPage, model: str,
            chunk_size: int) -> list[tuple[str, list[float]]] | None:
        cached = self._file(page, model, chunk_size)
        if not cached.exists():
            return None
        d = json.loads(cached.read_text(encoding="utf-8"))
        return [(c, v) for c, v in zip(d["chunks"], d["vectors"])]

    def put(self, page: FetchedPage, model: str, chunk_size: int,
            pairs: list[tuple[str, list[float]]]) -> None:
        self._file(page, model, chunk_size).write_text(json.dumps({
            "model": model,
            "chunk_size": chunk_size,
            "url": page.url,
            "chunks": [c for c, _ in pairs],
            "vectors": [v for _, v in pairs],
        }, ensure_ascii=False), encoding="utf-8")

    def match(self, query: list[float], model: str, chunk_size: int,
              pages: list[FetchedPage],
              k: int) -> list[tuple[FetchedPage, str, float]]:
        scored: list[tuple[FetchedPage, str, float]] = []
        for page in pages:
            for chunk, vec in self.get(page, model, chunk_size) or []:
                scored.append((page, chunk.strip(), cosine(query, vec)))
        scored.sort(key=lambda r: r[2], reverse=True)
        return scored[:k]
