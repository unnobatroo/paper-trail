"""page/vector cache on postgres + dense/lexical rank fusion you can inspect"""

import json

from sqlalchemy import text

from ...ml.retrieval import reciprocal_rank_fusion
from ...sources.fetch import FetchedPage
from ..indexing import content_key, fit_vector
from ..ports import PageStore, VectorIndex
from ..store import Repo

_CHUNKS = "FROM chunks c JOIN pages p ON p.id=c.page_id"


def _vector(values):
    return json.dumps(fit_vector(values))


class PostgresPageStore(Repo, PageStore):
    def get(self, url):
        row = self._one("SELECT url, title, text, published_on FROM pages WHERE url=:url", url=url)
        return FetchedPage(**row) if row else None

    def put(self, page):
        self._exec("INSERT INTO pages(url, title, text, published_on)"
                   " VALUES (:url, :title, :text, :published_on) ON CONFLICT(url) DO UPDATE"
                   " SET title=excluded.title, text=excluded.text,"
                   " published_on=excluded.published_on",
                   url=page.url, title=page.title, text=page.text, published_on=page.published_on)


class PostgresVectorIndex(Repo, VectorIndex):
    def __init__(self, database_url: str, ts_config: str = "simple", analyzer=None):
        super().__init__(database_url)
        self.ts_config = ts_config
        self.analyzer = analyzer

    def _key(self, page, model, chunk_size):
        analyzer_model = getattr(self.analyzer, "_model", "snowball")
        return model + ":" + content_key(model + analyzer_model, chunk_size, page.text)

    def _lemmas(self, text_):
        return " ".join(self.analyzer.analyze(text_).lemmas) if self.analyzer else text_

    def has(self, page, model, chunk_size):
        return self._one(f"SELECT 1 {_CHUNKS} WHERE p.url=:url AND c.embed_model=:key"
                         " AND c.chunk_index=0",
                         url=page.url, key=self._key(page, model, chunk_size)) is not None

    def get(self, page, model, chunk_size):
        rows = self._all(f"SELECT c.text, c.embedding::text AS embedding {_CHUNKS}"
                         " WHERE p.url=:url AND c.embed_model=:key ORDER BY c.chunk_index",
                         url=page.url, key=self._key(page, model, chunk_size))
        return [(r["text"], json.loads(r["embedding"])) for r in rows] or None

    def put(self, page, model, chunk_size, pairs):
        # do the model work before the transaction, no db lock waits on nlp
        lemmas = [self._lemmas(t) for t, _ in pairs]
        key = self._key(page, model, chunk_size)
        with self._engine.begin() as conn:
            pid = conn.execute(text("SELECT id FROM pages WHERE url=:url"),
                               {"url": page.url}).scalar()
            if pid is None:
                raise ValueError("cache the source page before its vectors")
            conn.execute(text("DELETE FROM chunks WHERE page_id=:pid AND embed_model=:key"),
                         {"pid": pid, "key": key})
            if pairs:
                conn.execute(text(
                    "INSERT INTO chunks(page_id, embed_model, chunk_index, text, embedding,"
                    " lemma_text) VALUES (:pid, :key, :i, :text, CAST(:vec AS vector), :lemma)"),
                    [{"pid": pid, "key": key, "i": i, "text": t, "vec": _vector(v), "lemma": lem}
                     for i, ((t, v), lem) in enumerate(zip(pairs, lemmas, strict=True))])

    def match(self, query, query_text, model, chunk_size, pages, k):
        if not pages or not any(query):
            return []
        by_url = {p.url: p for p in pages}
        if self.analyzer:
            # lemmas are stored pre-analyzed, so the 'simple' config is enough
            tsv, tsq = "c.lemma_search", "websearch_to_tsquery('simple', :terms)"
        else:
            tsv = "to_tsvector(CAST(:cfg AS regconfig), c.text)"
            tsq = "websearch_to_tsquery(CAST(:cfg AS regconfig), :terms)"
        params = {"q": _vector(query), "urls": list(by_url),
                  "models": [self._key(p, model, chunk_size) for p in pages],
                  "terms": self._lemmas(query_text), "cfg": self.ts_config,
                  "pool": max(k * 4, 20)}
        base = ("SELECT c.id, c.text, p.url,"
                " 1 - (c.embedding <=> CAST(:q AS vector)) AS similarity"
                f" {_CHUNKS} WHERE p.url IN :urls AND c.embed_model IN :models")
        # order by the bare cosine op or postgres won't use hnsw
        dense = self._all(base + " ORDER BY c.embedding <=> CAST(:q AS vector) LIMIT :pool",
                          **params)
        lexical = self._all(base + f" AND {tsv} @@ {tsq}"
                                   f" ORDER BY ts_rank_cd({tsv}, {tsq}) DESC, c.id LIMIT :pool",
                            **params)
        rows = {r["id"]: r for r in dense + lexical}
        fused = reciprocal_rank_fusion([[r["id"] for r in dense], [r["id"] for r in lexical]])
        order = sorted(fused, key=lambda i: (-fused[i], i))[:k]
        return [(by_url[rows[i]["url"]], rows[i]["text"], float(rows[i]["similarity"]))
                for i in order]
