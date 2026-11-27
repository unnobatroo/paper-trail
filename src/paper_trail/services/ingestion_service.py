"""ingestion: strategy pdf -> candidates waiting for review"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from ..domain.models import SourceDocument
from ..ml.extraction import LLMExtractor, NoExtractor
from ..repositories.store import PolicyRepository
from ..sources.parsers import PypdfDocumentParser


class IngestionService:
    def __init__(self, repo: PolicyRepository, extractor: LLMExtractor | NoExtractor, parser=None):
        self._repo = repo
        self._extractor = extractor
        self._parser = parser or PypdfDocumentParser()

    def ingest(self, pdf: str | Path | bytes, title: str, publisher: str,
               url: str = "", on_progress: Callable[[str], None] | None = None
               ) -> tuple[int, int]:
        """gives (document_id, candidates stored by this call). pdf is a path or raw bytes.

        each window of pages lands with its candidates in one transaction as soon as the
        model finishes it, so a retried job skips what's done. on_progress runs after every
        window: the job queue passes progress(), which raises once the lease is lost
        """
        doc_id = self._repo.add_document(SourceDocument(
            title=title, publisher=publisher, url=url,
        ))
        content = pdf if isinstance(pdf, bytes) else Path(pdf).read_bytes()
        pages = self._parser.pages(content)
        key = self._extractor.name
        # checkpoints belong to these bytes: the same url may serve a revised pdf next time
        digest = hashlib.sha256(content).hexdigest()
        done = self._repo.ingested_pages(doc_id, key, digest)
        # a page with no text is never sent or checkpointed: if its ocr failed, a later run
        # with working ocr must still be able to read it, and checking a blank costs nothing
        todo = [p for p in pages if p.page_number not in done and p.text.strip()]
        say = on_progress or (lambda _msg: None)
        finished = len(pages) - len(todo)
        say(f"page {finished}/{len(pages)}")
        n = 0
        # closing: a raise here (lost lease) cancels the windows not yet sent to the model
        with closing(self._extractor.extract_windows(todo)) as windows:
            for window, cands in windows:
                # receipts only count on the window's own pages, the ones it checkpoints
                page_text = {p.page_number: p.text for p in window}
                kept = []
                for c in cands:
                    c.document_id = doc_id
                    c.excerpt_on_page = bool(c.source_excerpt.strip()) and (
                        c.source_excerpt in page_text.get(c.source_page, ""))
                    if c.excerpt_on_page:
                        kept.append(c)
                n += self._repo.add_page_candidates(doc_id, key, digest, list(page_text),
                                                      kept)
                finished += len(window)
                say(f"page {finished}/{len(pages)}")
        return doc_id, n
