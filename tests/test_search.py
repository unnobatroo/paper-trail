"""Search stays inside the official allowlist."""

import json

from paper_trail.sources.web_search import FixtureSearch, allowed


def test_allowed_domains():
    assert allowed("https://jozsefvaros.hu/page")
    assert allowed("https://reszvetel.jozsefvaros.hu/x")
    assert allowed("https://rev8.hu/utcafasitas/")
    assert allowed("https://www.budapest.hu/x")
    assert not allowed("https://example.com/")
    assert not allowed("https://jozsefvaros.hu.evil.com/")


def test_fixture_search_filters_and_bounds(tmp_path):
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
    assert all(allowed(h.url) for h in hits)
