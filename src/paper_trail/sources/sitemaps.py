"""bounded sitemap/feed discovery, no search engine needed"""
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Collection
from urllib.parse import urljoin, urlsplit

from ..domain.models import OfficialSource
from .fetch import _read_capped, safe_get
from .web_search import allowed


class SourceDiscovery(ABC):
    @abstractmethod
    def discover(self, domains: Collection[str]) -> list[OfficialSource]: ...


class SitemapCrawler(SourceDiscovery):
    def __init__(self, max_maps: int = 20, max_urls: int = 200):
        self.max_maps, self.max_urls = max_maps, max_urls

    def discover(self, domains: Collection[str]) -> list[OfficialSource]:
        queue = deque(f"https://{d}/{name}" for d in sorted(domains)
                      for name in ["sitemap.xml", "feed/"])
        seen, documents = set(), {}
        while queue and len(seen) < self.max_maps and len(documents) < self.max_urls:
            url = queue.popleft()
            if url in seen or not allowed(url, domains):
                continue
            seen.add(url)
            try:
                response = safe_get(url, domains)
                response.raise_for_status()
                content = _read_capped(response)
                if content is None:
                    continue
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    continue
                root = ET.fromstring(content)
                is_index = root.tag.rsplit("}", 1)[-1] == "sitemapindex"
                for node in root.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    candidate = node.get("url") if tag == "enclosure" else (
                        node.get("href") or node.text if tag in {"loc", "link"} else None)
                    if not candidate:
                        continue
                    candidate = urljoin(url, candidate.strip())
                    if not allowed(candidate, domains):
                        continue
                    if is_index and tag == "loc":
                        if len(queue) < self.max_maps:
                            queue.append(candidate)
                    elif urlsplit(candidate).path.lower().endswith(".pdf"):
                        documents[candidate] = OfficialSource(
                            url=candidate, title=urlsplit(candidate).path.rsplit("/", 1)[-1],
                            publisher=urlsplit(candidate).hostname or "")
                        if len(documents) >= self.max_urls:
                            break
            except (OSError, ValueError, ET.ParseError):
                continue
        return list(documents.values())
