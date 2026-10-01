"""Source documents (the strategy PDF and friends) — by name, as bytes.

* `LocalDocumentStore` — the repo's `data/source_documents/` dir; the
  offline/dev path and the tests' fixture.
* `StorageDocumentStore` — a private Supabase Storage bucket, used when
  `SUPABASE_URL`/`SUPABASE_KEY` are configured, so no document bytes need
  to live in the deployed codebase.
"""

from __future__ import annotations

import logging
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

from supabase import Client

from ..infrastructure.supabase_client import create as create_supabase

log = logging.getLogger(__name__)

DEFAULT_BUCKET = "source-documents"


class DocumentStore(ABC):
    @abstractmethod
    def read(self, name: str) -> bytes | None:
        """Document bytes, or None when the store doesn't hold it."""

    @abstractmethod
    def write(self, name: str, data: bytes) -> None:
        """Store document bytes under `name` (overwrite is fine)."""

    @abstractmethod
    def delete(self, name: str) -> None:
        """Remove `name`; missing is fine."""

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        """All names in the store under `prefix`."""


class LocalDocumentStore(DocumentStore):
    def __init__(self, root: Path | str):
        self._root = Path(root)

    def read(self, name: str) -> bytes | None:
        path = self._root / name
        return path.read_bytes() if path.exists() else None

    def write(self, name: str, data: bytes) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / name).write_bytes(data)

    def delete(self, name: str) -> None:
        (self._root / name).unlink(missing_ok=True)

    def list(self, prefix: str = "") -> list[str]:
        if not self._root.exists():
            return []
        return sorted(p.name for p in self._root.glob(f"{prefix}*"))


class StorageDocumentStore(DocumentStore):
    def __init__(self, url: str, key: str, bucket: str = DEFAULT_BUCKET,
                 client: Client | None = None):
        self._bucket = bucket
        self._files = (client or create_supabase(url, key)).storage.from_(bucket)

    def read(self, name: str) -> bytes | None:
        try:
            return self._files.download(name)
        except Exception as exc:  # storage errors aren't typed per-cause
            log.warning("storage download %s failed: %s", name, exc)
            return None

    def write(self, name: str, data: bytes) -> None:
        ctype = (mimetypes.guess_type(name)[0]
                 or "application/octet-stream")
        self._files.upload(
            name, data, {"content-type": ctype, "upsert": "true"})

    def delete(self, name: str) -> None:
        try:
            self._files.remove([name])
        except Exception as exc:
            log.warning("storage remove %s failed: %s", name, exc)

    def list(self, prefix: str = "") -> list[str]:
        try:
            return sorted(
                item["name"] for item in self._files.list(prefix)
                if item.get("name"))
        except Exception as exc:
            log.warning("storage list %s failed: %s", prefix, exc)
            return []
