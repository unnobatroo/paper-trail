"""ingestion: strategy pdf -> candidates waiting for review"""

from __future__ import annotations

from pathlib import Path

from ..domain.models import SourceDocument
from ..ml.extraction import LLMExtractor, NoExtractor
from ..repositories.ports import PolicyStore
from ..sources.pdf import read_pages


class IngestionService:
    def __init__(self, repo: PolicyStore, extractor: LLMExtractor | NoExtractor, parser=None):
        self._repo = repo
        self._extractor = extractor
        self._parser = parser

    def ingest(self, pdf: str | Path | bytes, title: str, publisher: str,
               url: str = "") -> tuple[int, int]:
        """gives (document_id, candidate_count). pdf is a path or raw bytes"""
        doc_id = self._repo.add_document(SourceDocument(
            title=title, publisher=publisher, url=url,
        ))
        if self._parser is None:
            pages = read_pages(pdf)
        else:
            content = pdf if isinstance(pdf, bytes) else Path(pdf).read_bytes()
            pages = self._parser.parse(content).pages
        candidates = self._extractor.extract(pages)
        page_text = {p.page_number: p.text for p in pages}
        n = 0
        for c in candidates:
            c.document_id = doc_id
            c.excerpt_on_page = bool(c.source_excerpt.strip()) and (
                c.source_excerpt in page_text.get(c.source_page, ""))
            if not c.excerpt_on_page:
                continue
            self._repo.add_candidate(c)
            n += 1
        return doc_id, n
