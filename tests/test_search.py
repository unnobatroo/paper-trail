"""Search stays inside the official allowlist."""

import json

from paper_trail.sources.web_search import FixtureSearch, allowed

DOMAINS = {"jozsefvaros.hu", "rev8.hu", "budapest.hu"}


def test_allowed_domains():
    assert allowed("https://jozsefvaros.hu/page", DOMAINS)
    assert allowed("https://reszvetel.jozsefvaros.hu/x", DOMAINS)
    assert allowed("https://rev8.hu/utcafasitas/", DOMAINS)
    assert allowed("https://www.budapest.hu/x", DOMAINS)
    assert not allowed("https://example.com/", DOMAINS)
    assert not allowed("https://jozsefvaros.hu.evil.com/", DOMAINS)


def test_fixture_search_bounds_and_caller_filters(tmp_path):
    """The provider returns raw engine hits; the allowlist is the caller's
    job (evidence service). So: bounded at max_results, then filtered."""
    rows = [
        {"query_substring": "fa", "url": "https://rev8.hu/a", "title": "a"},
        {"query_substring": "fa", "url": "https://random.blog/x", "title": "off"},
        {"query_substring": "fa", "url": "https://rev8.hu/b", "title": "b"},
        {"query_substring": "fa", "url": "https://rev8.hu/c", "title": "c"},
        {"query_substring": "fa", "url": "https://rev8.hu/d", "title": "d"},
        {"query_substring": "fa", "url": "https://rev8.hu/e", "title": "e"},
        {"query_substring": "fa", "url": "https://rev8.hu/f", "title": "f"},
    ]
    f = tmp_path / "search_results.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    hits = FixtureSearch(f).search("fa site:rev8.hu", max_results=5)
    assert len(hits) == 5
    keep = [h for h in hits if allowed(h.url, DOMAINS)]
    assert len(keep) == 4
    assert all("rev8.hu" in h.url for h in keep)
