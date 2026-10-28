"""search providers: ddgs (no key) and a jsonl fixture for offline/tests

providers are dumb, the evidence service enforces the ssrf allowlist
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


def allowed(url: str, domains: Collection[str]) -> bool:
    """url on an allowed domain (or subdomain)?"""
    # hostname not netloc, "user@evil.test" / ":443" must not pass
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        ...


class DdgSearch(SearchProvider):
    """ddgs, two retries w/ backoff, total failure propagates so the caller can skip the domain"""

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        from ddgs import DDGS

        for attempt in range(3):
            try:
                hits: list[SearchHit] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        hits.append(SearchHit(
                            url=r.get("href", ""),
                            title=r.get("title", ""),
                            snippet=r.get("body", ""),
                        ))
                return hits
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        return []  # unreachable, last attempt re-raises


class FixtureSearch(SearchProvider):
    """cached results, one json object per line:

    {"query_substring": "utcafásítás", "url": "...", "title": "...", "snippet": "..."}
    hit when `query_substring` is in the query
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
            if r["query_substring"].lower() in query.lower()
        ]
        return hits[:max_results]


def get_search_provider(name: str, fixture_dir: Path) -> SearchProvider:
    if name == "fixture":
        return FixtureSearch(fixture_dir / "search_results.jsonl")
    return DdgSearch()
