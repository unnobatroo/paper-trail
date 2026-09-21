"""Web search restricted to the official-source allowlist.

Two providers behind one interface:

* `DdgSearch` — DuckDuckGo via the `ddgs` package, no API key needed.
* `FixtureSearch` — reads cached JSONL results (offline runs and tests).

Both return the same SearchHit objects; the pipeline treats them identically.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_DOMAINS = ("jozsefvaros.hu", "rev8.hu", "budapest.hu")


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


def allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        ...


class DdgSearch(SearchProvider):
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        from ddgs import DDGS

        hits: list[SearchHit] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results * 2):
                url = r.get("href", "")
                if not allowed(url):
                    continue
                hits.append(SearchHit(
                    url=url,
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                ))
                if len(hits) >= max_results:
                    break
        return hits


class FixtureSearch(SearchProvider):
    """Reads cached search results — one JSON object per line:

    {"query_substring": "utcafásítás", "url": "...", "title": "...", "snippet": "..."}
    A hit is returned when `query_substring` appears in the query.
    """

    def __init__(self, fixture_path: Path):
        self._rows = []
        if fixture_path.exists():
            for line in fixture_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._rows.append(json.loads(line))

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        hits = [
            SearchHit(url=r["url"], title=r.get("title", ""), snippet=r.get("snippet", ""))
            for r in self._rows
            if r["query_substring"].lower() in query.lower() and allowed(r["url"])
        ]
        return hits[:max_results]


def get_search_provider(name: str, fixture_dir: Path) -> SearchProvider:
    if name == "fixture":
        return FixtureSearch(fixture_dir / "search_results.jsonl")
    return DdgSearch()
