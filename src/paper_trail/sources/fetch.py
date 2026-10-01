"""Fetch and read allow-listed official pages and PDFs.

Not a crawler: given a URL already found by search (or listed in the official
document registry), download once and return plain text. HTML goes through
trafilatura, PDFs through pypdf. The allowlist is supplied by the caller —
it derives from the source registry, not from code.
"""

from __future__ import annotations

import io
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

import requests
import trafilatura
from pypdf import PdfReader

from .web_search import allowed

_HEADERS = {"User-Agent": "paper-trail/0.1 (municipal evidence research)"}
_TIMEOUT = 30


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    published_on: date | None = None


def fetch(url: str, allowed_domains: Collection[str]) -> FetchedPage | None:
    """Fetch one allow-listed URL. Returns None when unreadable/off-list."""
    if not allowed(url, allowed_domains):
        return None
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    # redirects are followed implicitly — re-check the allowlist on the
    # final URL so an on-list page can't point the fetcher off-list
    if not allowed(resp.url, allowed_domains):
        return None

    if url.lower().endswith(".pdf") or resp.headers.get("content-type", "").startswith(
        "application/pdf"
    ):
        return _read_pdf(url, resp.content)
    return _read_html(url, resp.text)


def _read_pdf(url: str, content: bytes) -> FetchedPage | None:
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return None
    if not text.strip():
        return None
    name = url.rsplit("/", 1)[-1].split("?")[0]
    return FetchedPage(url=url, title=name, text=text)


def _read_html(url: str, html: str) -> FetchedPage | None:
    # htmldate can crash on malformed dates (e.g. a +25:00 UTC offset in a
    # meta tag) — a bad date must not cost us the page
    try:
        meta = trafilatura.extract_metadata(html)
    except Exception:
        meta = None
    try:
        text = trafilatura.extract(html) or ""
    except Exception:
        return None
    if not text.strip():
        return None
    published = None
    if meta and meta.date:
        try:
            published = date.fromisoformat(meta.date)
        except (ValueError, TypeError):
            published = None
    return FetchedPage(
        url=url,
        title=meta.title if meta and meta.title else url,
        text=text,
        published_on=published,
    )
