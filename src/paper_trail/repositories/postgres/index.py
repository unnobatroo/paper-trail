"""page/vector cache on postgres + dense/lexical rank fusion you can inspect"""

import json

from ...ml.retrieval import reciprocal_rank_fusion
from ...sources.fetch import FetchedPage
from ..indexing import content_key, fit_vector
from ..ports import PageStore, VectorIndex
from .db import connect


def _vector(values):
    return json.dumps(fit_vector(values))


class PostgresPageStore(PageStore):
    def __init__(self, database_url: str):
        self.database_url = database_url

    def get(self, url):
        with connect(self.database_url) as conn:
            row = conn.execute("SELECT * FROM pages WHERE url=%s", (url,)).fetchone()
        if row:
            return FetchedPage(
                url=row["url"],
                title=row["title"],
                text=row["text"],
                published_on=row["published_on"],
            )
        return None

    def put(self, page):
        with connect(self.database_url) as conn:
            conn.execute(
                """INSERT INTO pages(url,title,text,published_on)
                VALUES(%s,%s,%s,%s) ON CONFLICT(url) DO UPDATE SET title=excluded.title,
                text=excluded.text,published_on=excluded.published_on""",
                (page.url, page.title, page.text, page.published_on),
            )


class PostgresVectorIndex(VectorIndex):
    def __init__(self, database_url: str, ts_config: str = "simple", analyzer=None):
        self.database_url = database_url
        self.ts_config = ts_config
        self.analyzer = analyzer

    def _key(self, page, model, chunk_size):
        analyzer_model = getattr(self.analyzer, "_model", "snowball")
        return model + ":" + content_key(model + analyzer_model, chunk_size, page.text)

    def has(self, page, model, chunk_size):
        with connect(self.database_url) as conn:
            return bool(
                conn.execute(
                    """SELECT 1 FROM chunks c JOIN pages p ON p.id=c.page_id
                WHERE p.url=%s AND c.embed_model=%s AND c.chunk_index=0""",
                    (page.url, self._key(page, model, chunk_size)),
                ).fetchone()
            )

    def get(self, page, model, chunk_size):
        with connect(self.database_url) as conn:
            rows = conn.execute(
                """SELECT c.text,c.embedding::text FROM chunks c
                JOIN pages p ON p.id=c.page_id WHERE p.url=%s AND c.embed_model=%s
                ORDER BY c.chunk_index""",
                (page.url, self._key(page, model, chunk_size)),
            ).fetchall()
        return [(r["text"], json.loads(r["embedding"])) for r in rows] or None

    def put(self, page, model, chunk_size, pairs):
        # do the model work before the transaction, no db lock waits on nlp
        lemmas = [
            " ".join(self.analyzer.analyze(text).lemmas) if self.analyzer else text
            for text, _ in pairs
        ]
        with connect(self.database_url) as conn:
            pid = conn.execute("SELECT id FROM pages WHERE url=%s", (page.url,)).fetchone()
            if not pid:
                raise ValueError("cache the source page before its vectors")
            key = self._key(page, model, chunk_size)
            conn.execute("DELETE FROM chunks WHERE page_id=%s AND embed_model=%s", (pid["id"], key))
            for i, ((text, vec), lemma) in enumerate(zip(pairs, lemmas, strict=True)):
                conn.execute(
                    """INSERT INTO chunks
                    (page_id,embed_model,chunk_index,text,embedding,lemma_text)
                    VALUES(%s,%s,%s,%s,%s::vector,%s)""",
                    (pid["id"], key, i, text, _vector(vec), lemma),
                )

    def match(self, query, query_text, model, chunk_size, pages, k):
        if not pages or not any(query):
            return []
        by_url = {p.url: p for p in pages}
        models = [self._key(p, model, chunk_size) for p in pages]
        query_lemmas = (
            " ".join(self.analyzer.analyze(query_text).lemmas) if self.analyzer else query_text
        )
        pool = max(k * 4, 20)
        with connect(self.database_url) as conn:
            # order by the bare cosine op or postgres won't use hnsw
            dense = conn.execute(
                """SELECT c.id,c.text,p.url,
                    1-(c.embedding <=> %s::vector) similarity
                FROM chunks c JOIN pages p ON p.id=c.page_id
                WHERE p.url=ANY(%s) AND c.embed_model=ANY(%s)
                ORDER BY c.embedding <=> %s::vector LIMIT %s""",
                (_vector(query), list(by_url), models, _vector(query), pool),
            ).fetchall()
            if self.analyzer:
                lexical = conn.execute(
                    """SELECT c.id,c.text,p.url,
                        1-(c.embedding <=> %s::vector) similarity
                    FROM chunks c JOIN pages p ON p.id=c.page_id
                    WHERE p.url=ANY(%s) AND c.embed_model=ANY(%s)
                        AND c.lemma_search @@ websearch_to_tsquery('simple',%s)
                    ORDER BY ts_rank_cd(c.lemma_search,websearch_to_tsquery('simple',%s)) DESC,c.id
                    LIMIT %s""",
                    (_vector(query), list(by_url), models, query_lemmas, query_lemmas, pool),
                ).fetchall()
            else:
                lexical = conn.execute(
                    """SELECT c.id,c.text,p.url,
                        1-(c.embedding <=> %s::vector) similarity
                    FROM chunks c JOIN pages p ON p.id=c.page_id
                    WHERE p.url=ANY(%s) AND c.embed_model=ANY(%s)
                        AND to_tsvector(%s::regconfig,c.text) @@
                            websearch_to_tsquery(%s::regconfig,%s)
                    ORDER BY ts_rank_cd(to_tsvector(%s::regconfig,c.text),
                        websearch_to_tsquery(%s::regconfig,%s)) DESC,c.id LIMIT %s""",
                    (
                        _vector(query),
                        list(by_url),
                        models,
                        self.ts_config,
                        self.ts_config,
                        query_text,
                        self.ts_config,
                        self.ts_config,
                        query_text,
                        pool,
                    ),
                ).fetchall()
        rows = {r["id"]: r for r in dense + lexical}
        rankings = [[r["id"] for r in dense], [r["id"] for r in lexical]]
        fused = reciprocal_rank_fusion(rankings)
        order = sorted(fused, key=lambda i: (-fused[i], i))[:k]
        return [
            (by_url[rows[i]["url"]], rows[i]["text"], float(rows[i]["similarity"])) for i in order
        ]
