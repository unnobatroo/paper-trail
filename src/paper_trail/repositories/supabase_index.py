"""Postgres-backed system caches — the Supabase side of `cache.py`.

`pages`  replaces the fetched/*.txt page cache (one row per URL, text is
         immutable once stored);
`chunks` + the `match_chunks` RPC replace embeddings/*.json *and* the
         in-Python cosine loop — top-k runs inside Postgres via pgvector.

Needs `supabase/migrations/002_pgvector.sql`. Like `supabase_store.py`,
the client is stateless HTTP and safe to share across threads.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from supabase import Client

from ..infrastructure.supabase_client import create as create_supabase
from ..sources.fetch import FetchedPage
from .cache import LEX_WEIGHT, PageStore, VectorIndex, pad_vector
from .supabase_store import select_all

log = logging.getLogger(__name__)

# rows per insert batch — chunk rows carry ~20 KB of vector text each
_BATCH = 200


def _vec_literal(vec: list[float]) -> str:
    """pgvector's text form: '[0.1,0.2,...]'. Sending a string avoids
    PostgREST JSON-array coercion edge cases."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _parse_vec(raw) -> list[float]:
    if isinstance(raw, str):
        return json.loads(raw)
    return [float(x) for x in raw]


class SupabasePageStore(PageStore):
    def __init__(self, url: str, key: str, client: Client | None = None):
        self._db = client or create_supabase(url, key)

    def get(self, url: str) -> FetchedPage | None:
        res = (self._db.table("pages")
               .select("url,title,text,published_on")
               .eq("url", url).execute())
        if not res.data:
            return None
        r = res.data[0]
        return FetchedPage(
            url=r["url"], title=r["title"], text=r["text"],
            published_on=(date.fromisoformat(r["published_on"])
                          if r["published_on"] else None),
        )

    def put(self, page: FetchedPage) -> None:
        self._db.table("pages").upsert({
            "url": page.url,
            "title": page.title,
            "text": page.text,
            "published_on": (page.published_on.isoformat()
                             if page.published_on else None),
        }, on_conflict="url").execute()

    def page_id(self, url: str) -> int | None:
        res = (self._db.table("pages").select("id")
               .eq("url", url).execute())
        return res.data[0]["id"] if res.data else None


class SupabaseVectorIndex(VectorIndex):
    def __init__(self, url: str, key: str, client: Client | None = None,
                 ts_config: str = "hungarian"):
        self._db = client or create_supabase(url, key)
        self._ts_config = ts_config
        self._page_ids: dict[str, int] = {}

    def _page_id(self, url: str) -> int | None:
        # cache hits only — a miss may precede the row's creation, and a
        # cached None would make a later put() silently drop its vectors
        if url in self._page_ids:
            return self._page_ids[url]
        res = (self._db.table("pages").select("id")
               .eq("url", url).execute())
        if not res.data:
            return None
        self._page_ids[url] = res.data[0]["id"]
        return res.data[0]["id"]

    def has(self, page: FetchedPage, model: str, chunk_size: int) -> bool:
        pid = self._page_id(page.url)
        if pid is None:
            return False
        res = (self._db.table("chunks").select("id")
               .eq("page_id", pid).eq("embed_model", model)
               .limit(1).execute())
        return bool(res.data)

    def get(self, page: FetchedPage, model: str,
            chunk_size: int) -> list[tuple[str, list[float]]] | None:
        pid = self._page_id(page.url)
        if pid is None:
            return None
        # paginate — PostgREST caps each response (default 1000 rows) and
        # a big document can hold more chunks than that
        res = select_all(
            self._db.table("chunks")
            .select("text,embedding")
            .eq("page_id", pid).eq("embed_model", model)
            .order("chunk_index"))
        if not res:
            return None
        return [(r["text"], _parse_vec(r["embedding"])) for r in res]

    def put(self, page: FetchedPage, model: str, chunk_size: int,
            pairs: list[tuple[str, list[float]]]) -> None:
        pid = self._page_id(page.url)
        if pid is None or not pairs:
            return
        rows = [{
            "page_id": pid,
            "embed_model": model,
            "chunk_index": i,
            "text": text,
            "embedding": _vec_literal(pad_vector(vec)),
        } for i, (text, vec) in enumerate(pairs)]
        for i in range(0, len(rows), _BATCH):
            (self._db.table("chunks")
             .upsert(rows[i: i + _BATCH],
                     on_conflict="page_id,embed_model,chunk_index")
             .execute())

    def match(self, query: list[float], query_text: str, model: str,
              chunk_size: int, pages: list[FetchedPage],
              k: int) -> list[tuple[FetchedPage, str, float]]:
        by_url = {p.url: p for p in pages}
        try:
            res = self._db.rpc("match_chunks_hybrid", {
                "query_embedding": _vec_literal(pad_vector(query)),
                "query_text": query_text,
                "model": model,
                "match_count": k,
                "page_urls": [p.url for p in pages],
                "lex_weight": LEX_WEIGHT,
                "lex_config": self._ts_config,
            }).execute()
        except Exception as exc:
            # PGRST202: function missing — migration 006 not applied yet.
            # Degrade to dense-only rather than failing the evidence run.
            if getattr(exc, "code", "") != "PGRST202":
                raise
            log.warning("match_chunks_hybrid missing — run "
                        "supabase/migrations/006_hybrid_search.sql; "
                        "falling back to dense-only match_chunks")
            res = self._db.rpc("match_chunks", {
                "query_embedding": _vec_literal(pad_vector(query)),
                "model": model,
                "match_count": k,
                "page_urls": [p.url for p in pages],
            }).execute()
        out = []
        for r in res.data:
            page = by_url.get(r["page_url"])
            if page is not None:
                out.append((page, r["chunk_text"].strip(),
                            float(r["similarity"])))
        return out
