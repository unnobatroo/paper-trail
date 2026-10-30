"""fetch + read allowlisted official pages and pdfs

not a crawler: a url from search or the registry, downloaded once, plain text out.
html via trafilatura, pdfs via the parsers
"""

from __future__ import annotations

import io
import ipaddress
import socket
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlsplit

import charset_normalizer
import requests
import trafilatura
from pypdf import PdfReader

from .web_search import allowed

_HEADERS = {"User-Agent": "paper-trail/0.1 (municipal evidence research)"}
_TIMEOUT = 30
_MAX_BYTES = 25 * 1024 * 1024  # biggest strategy pdfs are ~10mb


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    published_on: date | None = None


def fetch(url: str, allowed_domains: Collection[str], parser=None) -> FetchedPage | None:
    """fetch one allowlisted url, None if unreadable or off-list"""
    if not allowed(url, allowed_domains):
        return None
    try:
        resp = safe_get(url, allowed_domains)
    except requests.RequestException:
        return None
    # streamed, so close it ourselves or a 404 leaks the socket
    with resp:
        try:
            resp.raise_for_status()
            content = _read_capped(resp)
        except requests.RequestException:
            return None
    if content is None:
        return None
    # redirects get followed, so recheck the allowlist on the final url
    if not allowed(resp.url, allowed_domains):
        return None

    if url.lower().endswith(".pdf") or resp.headers.get("content-type", "").startswith(
            "application/pdf"
    ):
        return _read_pdf(url, content, parser)
    return _read_html(url, _decode(content, resp.encoding))


def _decode(content: bytes, declared: str | None) -> str:
    """declared charset if python knows it, else let charset_normalizer guess.
    a bogus header shouldn't sink the whole search
    """
    if declared:
        try:
            return content.decode(declared, errors="replace")
        except LookupError:
            pass
    best = charset_normalizer.from_bytes(content).best()
    return str(best) if best is not None else content.decode("utf-8", errors="replace")


def _read_capped(resp: requests.Response) -> bytes | None:
    """body up to _MAX_BYTES, None past it, a runaway download shouldn't pin a worker"""
    buf = bytearray()
    for chunk in resp.iter_content(64 * 1024):
        buf += chunk
        if len(buf) > _MAX_BYTES:
            resp.close()
            return None
    return bytes(buf)


def _read_pdf(url: str, content: bytes, parser=None) -> FetchedPage | None:
    try:
        if parser is not None:
            text = parser.parse(content).markdown
        else:
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(
                f"<!-- page {i + 1} -->\n{p.extract_text() or chr(32)}"
                for i, p in enumerate(reader.pages))
    except Exception:
        return None
    if not text.strip():
        return None
    name = url.rsplit("/", 1)[-1].split("?")[0]
    return FetchedPage(url=url, title=name, text=text)


def _read_html(url: str, html: str) -> FetchedPage | None:
    # htmldate chokes on junk dates (+25:00 lol), a bad date shouldn't cost the page
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


def safe_get(url: str, domains: Collection[str]) -> requests.Response:
    for _ in range(6):
        if not allowed(url, domains):
            raise requests.RequestException("off-domain source redirect")
        host = urlsplit(url).hostname
        try:
            addresses = socket.getaddrinfo(host, None)
        except OSError as exc:
            raise requests.RequestException("source DNS failed") from exc
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise requests.RequestException("source resolves to a private address")
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT,
                                stream=True, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            following = urljoin(url, response.headers.get("Location", ""))
            response.close()
            url = following
        else:
            return response
    raise requests.RequestException("too many source redirects")
