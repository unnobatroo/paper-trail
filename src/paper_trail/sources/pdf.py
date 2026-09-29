"""Deterministic PDF text extraction — one DocumentPage per PDF page."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from ..domain.models import DocumentPage


def read_pages(source: str | Path | bytes | io.BytesIO) -> list[DocumentPage]:
    """`source` is a filesystem path or the document bytes themselves —
    the latter lets ingestion read straight from object storage."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    reader = PdfReader(source if isinstance(source, io.BytesIO) else str(source))
    pages = []
    for i, page in enumerate(reader.pages):
        pages.append(DocumentPage(page_number=i + 1, text=page.extract_text() or ""))
    return pages
