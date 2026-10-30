"""plain pdf text, one DocumentPage per page"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from ..domain.models import DocumentPage


def read_pages(source: str | Path | bytes) -> list[DocumentPage]:
    """source is a path or the raw bytes"""
    reader = PdfReader(io.BytesIO(source) if isinstance(source, bytes) else source)
    return [DocumentPage(page_number=i, text=p.extract_text() or "")
            for i, p in enumerate(reader.pages, 1)]
