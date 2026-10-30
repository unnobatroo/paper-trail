"""plain pdf text, one DocumentPage per page"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from ..domain.models import DocumentPage


def read_pages(source: str | Path | bytes | io.BytesIO) -> list[DocumentPage]:
    """source is a path or the raw bytes"""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    reader = PdfReader(source if isinstance(source, io.BytesIO) else str(source))
    pages = []
    for i, page in enumerate(reader.pages):
        pages.append(DocumentPage(page_number=i + 1, text=page.extract_text() or ""))
    return pages
