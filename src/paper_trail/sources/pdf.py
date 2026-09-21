"""Deterministic PDF text extraction — one DocumentPage per PDF page."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from ..domain.models import DocumentPage


def read_pages(path: str | Path) -> list[DocumentPage]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        pages.append(DocumentPage(page_number=i + 1, text=page.extract_text() or ""))
    return pages
