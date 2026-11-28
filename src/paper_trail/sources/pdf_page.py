"""one page of a source pdf: rendered to an image, with the rectangles a quote covers on it

The review app shows the page a quote was read from and marks the quote. The city's own server
can't be used for that from the browser (no CORS, no range requests, megabytes per file), so the
api fetches the pdf, finds the quote in the page's text and draws the page, and the browser only
gets a small image and a few rectangles.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import pypdfium2 as pdfium
import requests

from .fetch import safe_get

MAX_PDF_BYTES = 40_000_000
# when the whole quote can't be found, its longest opening that can still marks something useful,
# but under this many letters a match is as likely to be chance as the quote
_MIN_RUN = 20


class PdfUnavailable(Exception):
    """the pdf could not be fetched, was not a pdf, or has no such page"""


@dataclass(frozen=True)
class Box:
    """a rectangle as fractions of the page, from its top left corner"""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class PageView:
    width: float
    height: float
    boxes: list[Box]
    found: bool


@lru_cache(maxsize=4)
def download(url: str) -> bytes:
    """the pdf at `url`, kept for the next page of the same file. only its own host is followed"""
    host = urlsplit(url).hostname
    if urlsplit(url).scheme not in ("http", "https") or not host:
        raise PdfUnavailable("not a web address")
    try:
        response = safe_get(url, {host})
        with response:
            if response.status_code != 200:
                raise PdfUnavailable(f"the source answered {response.status_code}")
            body = bytearray()
            for chunk in response.iter_content(1 << 16):
                body += chunk
                if len(body) > MAX_PDF_BYTES:
                    raise PdfUnavailable("the pdf is too large")
    except requests.RequestException as exc:
        raise PdfUnavailable(str(exc)) from exc
    if not body.startswith(b"%PDF"):
        raise PdfUnavailable("the address is not a pdf")
    return bytes(body)


def _letters(text: str) -> tuple[str, list[int]]:
    """letters and digits only, lower case, each with where it sits in `text`: quotes and the
    page's own text differ in line breaks, hyphens and spacing, never in the words themselves"""
    kept, where = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch).casefold():
            if c.isalnum():
                kept.append(c)
                where.append(i)
    return "".join(kept), where


Rect = tuple[float, float, float, float]


def _lines(boxes: list[Rect]) -> list[Rect]:
    """character boxes (left, bottom, right, top) merged into one rectangle per line of text"""
    merged: list[list[float]] = []
    for left, bottom, right, top in boxes:
        if right <= left or top <= bottom:
            continue
        last = merged[-1] if merged else None
        height = top - bottom
        middle = (bottom + top) / 2
        # same line: the vertical middle sits within the last box, and the gap is small
        on_line = last and last[1] - height / 2 <= middle <= last[3] + height / 2
        if last and on_line and left - last[2] < height * 2:
            last[0], last[2] = min(last[0], left), max(last[2], right)
            last[1], last[3] = min(last[1], bottom), max(last[3], top)
        else:
            merged.append([left, bottom, right, top])
    return [tuple(m) for m in merged]  # type: ignore[misc]


def locate(pdf: bytes, page_number: int, quote: str) -> PageView:
    """where `quote` sits on page `page_number` (1-based), as rectangles; `found` is False and the
    list empty when the page's text doesn't contain it"""
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError as exc:
        raise PdfUnavailable("the file could not be read as a pdf") from exc
    with document:
        if not 1 <= page_number <= len(document):
            raise PdfUnavailable(f"the pdf has no page {page_number}")
        page = document[page_number - 1]
        width, height = page.get_size()
        textpage = page.get_textpage()
        page_text = textpage.get_text_range()
        haystack, where = _letters(page_text)
        needle, _ = _letters(quote)
        start = haystack.find(needle) if needle else -1
        if start < 0 and len(needle) > _MIN_RUN and haystack.find(needle[:_MIN_RUN]) >= 0:
            # an opening is present or absent as a whole, so the longest one can be bisected
            low, high = _MIN_RUN, len(needle) - 1
            while low < high:
                mid = (low + high + 1) // 2
                low, high = (mid, high) if haystack.find(needle[:mid]) >= 0 else (low, mid - 1)
            needle = needle[:low]
            start = haystack.find(needle)
        if start < 0:
            return PageView(width, height, [], False)
        first, last = where[start], where[start + len(needle) - 1]
        spans = range(first, last + 1)
        chars = [textpage.get_charbox(i) for i in spans if not page_text[i].isspace()]
    boxes = [
        Box(x=left / width, y=1 - top / height, w=(right - left) / width, h=(top - bottom) / height)
        for left, bottom, right, top in _lines(chars)
    ]
    return PageView(width, height, boxes, True)


def render(pdf: bytes, page_number: int, scale: float = 1.6) -> bytes:
    """the page as a webp image"""
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError as exc:
        raise PdfUnavailable("the file could not be read as a pdf") from exc
    with document:
        if not 1 <= page_number <= len(document):
            raise PdfUnavailable(f"the pdf has no page {page_number}")
        image = document[page_number - 1].render(scale=scale).to_pil()
    out = io.BytesIO()
    image.save(out, "WEBP", quality=82)
    return out.getvalue()
