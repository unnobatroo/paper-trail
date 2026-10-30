"""search providers: searxng, ddgs (no key) and a jsonl fixture for tests

providers are dumb, the evidence service owns the ssrf allowlist
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_incrementing


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str


def allowed(url: str, domains: Collection[str]) -> bool:
    """url on an allowed domain (or subdomain)?"""
    # hostname not netloc, "user@evil.test" / ":443" must not sneak through
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]: ...


class DdgSearch:
    """ddgs, two retries with backoff, a total failure bubbles up so the caller skips the domain"""

    @retry(stop=stop_after_attempt(3), wait=wait_incrementing(start=1.5, increment=1.5),
           reraise=True)
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return [SearchHit(url=r.get("href", ""), title=r.get("title", ""),
                              snippet=r.get("body", ""))
                    for r in ddgs.text(query, max_results=max_results)]


class FixtureSearch:
    """cached results, one json object per line:

        {"query_substring": "utcafásítás", "url": "...", "title": "...", "snippet": "..."}

    hit when query_substring is in the query
    """

    def __init__(self, fixture_path: Path):
        text = fixture_path.read_text(encoding="utf-8") if fixture_path.exists() else ""
        self._rows = [json.loads(line) for line in text.splitlines() if line.strip()]

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        hits = [
            SearchHit(url=r["url"], title=r.get("title", ""), snippet=r.get("snippet", ""))
            for r in self._rows
            if r["query_substring"].lower() in query.lower()
        ]
        return hits[:max_results]


def get_search_provider(name: str, fixture_dir: Path, searxng_url: str = "",
                        domains: Collection[str] = ()) -> SearchProvider:
    if name == "fixture":
        return FixtureSearch(fixture_dir / "search_results.jsonl")
    if name == "searxng":
        return SearxngSearchProvider(searxng_url, domains)
    return DdgSearch()


class SearxngSearchProvider:
    """private searxng, one request per scoped domain

    the evidence service scopes each query with site:<domain> from its allowlist. first
    site token = the scope, any later one came from commitment text and gets dropped.
    results off the scope are tossed, the fetch allowlist is still the hard wall
    """

    def __init__(self, base_url: str, domains: Collection[str] = (), timeout: float = 20):
        self.base_url = base_url.rstrip("/")
        self.domains = tuple(domains)  # used only for unscoped queries
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        scope = re.match(r"\s*site:(\S+)", query)
        terms = re.sub(r"\bsite:\S+", "", query).strip()
        domains = (scope.group(1).lower(),) if scope else self.domains
        hits, seen = [], set()
        for domain in domains:
            response = requests.get(self.base_url + "/search", params={
                "q": f"site:{domain} {terms}", "format": "json"}, timeout=self.timeout)
            response.raise_for_status()
            for row in response.json().get("results", []):
                url = row.get("url", "")
                if url not in seen and allowed(url, domains):
                    seen.add(url)
                    hits.append(SearchHit(url, row.get("title", ""), row.get("content", "")))
        return hits[:max_results]
