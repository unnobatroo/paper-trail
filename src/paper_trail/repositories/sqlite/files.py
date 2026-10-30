"""file caches for sqlite/offline/tests, json per page. same deal as postgres/index.py"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

from ...ml.retrieval import reciprocal_rank_fusion
from ...sources.fetch import FetchedPage
from ..indexing import (
    content_key,
    lexical_scores,
    stemmer_for,
    url_key,
)
from ..ports import PageStore, VectorIndex


class FilePageStore(PageStore):
    """<cache>/<url_hash>.txt + .json"""

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
    """<cache>/embeddings/<content_hash>.json: chunks + vectors"""

    def __init__(self, cache_dir: Path, stemmer_language: str = "english", analyzer=None):
        self._dir = Path(cache_dir) / "embeddings"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._stem = stemmer_for(stemmer_language)
        self._analyzer = analyzer

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
        return [(c, v) for c, v in zip(d["chunks"], d["vectors"], strict=True)]

    def put(self, page: FetchedPage, model: str, chunk_size: int,
            pairs: list[tuple[str, list[float]]]) -> None:
        self._file(page, model, chunk_size).write_text(json.dumps({
            "model": model,
            "chunk_size": chunk_size,
            "url": page.url,
            "chunks": [c for c, _ in pairs],
            "vectors": [v for _, v in pairs],
        }, ensure_ascii=False), encoding="utf-8")

    def match(self, query: list[float], query_text: str, model: str,
              chunk_size: int, pages: list[FetchedPage],
              k: int) -> list[tuple[FetchedPage, str, float]]:
        flat: list[tuple[FetchedPage, str]] = []
        vecs: list[list[float]] = []
        for page in pages:
            for chunk, vec in (self.get(page, model, chunk_size) or []):
                flat.append((page, chunk))
                vecs.append(vec)
        q = np.asarray(query, dtype=np.float32)
        qn = np.linalg.norm(q)
        if not flat or not qn:
            return []
        pv = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(pv, axis=1)
        norms[norms == 0] = 1.0
        dense = pv @ q / (norms * qn)
        lex = lexical_scores(query_text, [c for _, c in flat],
                             self._stem, self._analyzer)
        rankings = [np.argsort(-dense, kind="stable").tolist()]
        if np.any(lex > 0):
            rankings.append([int(i) for i in np.argsort(-lex, kind="stable") if lex[i] > 0])
        fused = reciprocal_rank_fusion(rankings)
        order = sorted(fused, key=lambda i: (-fused[i], i))[:k]
        # raw cosine feeds the relationship hint, rrf only orders candidates
        return [(flat[i][0], flat[i][1].strip(), float(dense[i]))
                for i in order]
