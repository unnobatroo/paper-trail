"""source documents by name, a plain directory"""

from __future__ import annotations

from pathlib import Path


class DocumentStore:
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

    def list(self) -> list[str]:
        return sorted(p.name for p in self._root.glob("*")) if self._root.exists() else []
