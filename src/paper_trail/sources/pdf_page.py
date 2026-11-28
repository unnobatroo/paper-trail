"""one page of a source pdf: rendered to an image, with the rectangles a quote covers on it

The review app shows the page a quote was read from and marks the quote. The city's own server
can't be used for that from the browser (no CORS, no range requests, megabytes per file), so the
api fetches the pdf, finds the quote in the page's text and draws the page, and the browser only
gets a small image and a few rectangles. pypdf reads text but can't draw a page or say where a
character sits, hence pdfium (the engine Chrome's own viewer uses).
"""

from __future__ import annotations

import io
import threading
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
# pdfium keeps global state and is not thread-safe; the api serves its sync routes from a pool
_PDFIUM = threading.Lock()


class PdfUnavailable(Exception):
    """the pdf could not be fetched or read"""


class PageMissing(PdfUnavailable):
    """the pdf has no such page"""


@dataclass(frozen=True)
class Box:
    """a rectangle as fractions of the page as displayed, from its top left corner"""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class PageView:
    width: float
    height: float
    boxes: tuple[Box, ...]
    found: bool


@lru_cache(maxsize=2)
def download(url: str) -> bytes:
    """the pdf at `url`, kept for the next page of the same file. only its own host is followed"""
    host = urlsplit(url).hostname
    if urlsplit(url).scheme not in ("http", "https") or not host:
        raise PdfUnavailable("not a web address")
    chunks: list[bytes] = []
    try:
        with safe_get(url, {host}) as response:
            if response.status_code != 200:
                raise PdfUnavailable(f"the source answered {response.status_code}")
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > MAX_PDF_BYTES:
                raise PdfUnavailable("the pdf is too large")
            size = 0
            for chunk in response.iter_content(1 << 16):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise PdfUnavailable("the pdf is too large")
                chunks.append(chunk)
    except requests.RequestException as exc:
        raise PdfUnavailable(str(exc)) from exc
    body = b"".join(chunks)
    if not body.startswith(b"%PDF"):
        raise PdfUnavailable("the address is not a pdf")
    return body


@lru_cache(maxsize=64)
def highlight(url: str, page_number: int, quote: str) -> PageView:
    """`locate` for the pdf at `url`; the same quote on the same page is only looked for once"""
    return locate(download(url), page_number, quote)


@lru_cache(maxsize=32)
def page_image(url: str, page_number: int) -> bytes:
    """`render` for the pdf at `url`; a page is only drawn once"""
    return render(download(url), page_number)


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


def _on_display(rect: Rect, crop: Rect, rotation: int) -> Box:
    """a rectangle in the page's own coordinates (points, origin bottom left, unrotated) as
    fractions of the page as it is displayed: cropped to its crop box and turned by /Rotate"""
    crop_left, crop_bottom, crop_right, crop_top = crop
    width, height = crop_right - crop_left, crop_top - crop_bottom

    def turn(x: float, y: float) -> tuple[float, float]:
        u, v = (x - crop_left) / width, (crop_top - y) / height  # from the top left, unrotated
        # /Rotate turns the page clockwise for display
        return {90: (1 - v, u), 180: (1 - u, 1 - v), 270: (v, 1 - u)}.get(rotation, (u, v))

    left, bottom, right, top = rect
    (x1, y1), (x2, y2) = turn(left, top), turn(right, bottom)
    return Box(x=min(x1, x2), y=min(y1, y2), w=abs(x2 - x1), h=abs(y2 - y1))


def _open(pdf: bytes, page_number: int) -> tuple[pdfium.PdfDocument, pdfium.PdfPage]:
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError as exc:
        raise PdfUnavailable("the file could not be read as a pdf") from exc
    if not 1 <= page_number <= len(document):
        document.close()
        raise PageMissing(f"the pdf has no page {page_number}")
    return document, document[page_number - 1]


def locate(pdf: bytes, page_number: int, quote: str) -> PageView:
    """where `quote` sits on page `page_number` (1-based), as rectangles; `found` is False and
    there are none when the page's text doesn't contain it"""
    with _PDFIUM:
        document, page = _open(pdf, page_number)
        with document:
            width, height = page.get_size()
            crop, rotation = page.get_cropbox(), page.get_rotation()
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
                return PageView(width, height, (), False)
            first, last = where[start], where[start + len(needle) - 1]
            # pdfium counts characters as it stores them; never ask past the end
            spans = range(first, min(last + 1, textpage.count_chars()))
            chars = [textpage.get_charbox(i) for i in spans if not page_text[i].isspace()]
    boxes = tuple(_on_display(r, crop, rotation) for r in _lines(chars))
    return PageView(width, height, boxes, bool(boxes))


def render(pdf: bytes, page_number: int, scale: float = 1.6) -> bytes:
    """the page as it is displayed (cropped and turned), as a webp image"""
    with _PDFIUM:
        document, page = _open(pdf, page_number)
        with document:
            image = page.render(scale=scale).to_pil()
    out = io.BytesIO()
    image.save(out, "WEBP", quality=82)
    return out.getvalue()
