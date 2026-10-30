"""source documents by name, as bytes. LocalDocumentStore = a plain directory"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_BUCKET = "source-documents"


class DocumentStore(ABC):
    @abstractmethod
    def read(self, name: str) -> bytes | None:
        """bytes, or None if we don't have it"""

    @abstractmethod
    def write(self, name: str, data: bytes) -> None:
        """store bytes under name, overwriting is fine"""

    @abstractmethod
    def delete(self, name: str) -> None:
        """remove name, missing is fine"""

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        """every name under prefix"""


class LocalDocumentStore(DocumentStore):
    def __init__(self, root: Path | str):
        self._root = Path(root)

    def _path(self, name: str) -> Path:
        # names come from the api, keep them inside the store dir
        path = (self._root / name).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"document name escapes the store: {name!r}")
        return path

    def read(self, name: str) -> bytes | None:
        path = self._path(name)
        return path.read_bytes() if path.exists() else None

    def write(self, name: str, data: bytes) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._path(name).write_bytes(data)

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def list(self, prefix: str = "") -> list[str]:
        if not self._root.exists():
            return []
        return sorted(p.name for p in self._root.glob(f"{prefix}*"))
