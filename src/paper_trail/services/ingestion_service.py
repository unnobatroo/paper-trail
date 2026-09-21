"""Ingestion: strategy PDF → reviewed extraction candidates."""

from __future__ import annotations

from pathlib import Path

from ..domain.models import SourceDocument
from ..ml.extraction import Extractor, excerpt_found
from ..repositories.store import PolicyRepository
from ..sources.pdf import read_pages


class IngestionService:
    def __init__(self, repo: PolicyRepository, extractor: Extractor):
        self._repo = repo
        self._extractor = extractor

    def ingest(self, pdf_path: str | Path, title: str, publisher: str,
               url: str = "") -> tuple[int, int]:
        """Returns (document_id, candidate_count)."""
        path = Path(pdf_path)
        doc_id = self._repo.add_document(SourceDocument(
            title=title, publisher=publisher, url=url,
        ))
        pages = read_pages(path)
        candidates = self._extractor.extract(pages)
        page_text = {p.page_number: p.text for p in pages}
        n = 0
        for c in candidates:
            c.document_id = doc_id
            if c.excerpt_on_page is None:
                c.excerpt_on_page = excerpt_found(
                    page_text.get(c.source_page, ""), c.source_excerpt
                )
            self._repo.add_candidate(c)
            n += 1
        return doc_id, n
