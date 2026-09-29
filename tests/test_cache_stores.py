"""PageStore / VectorIndex contract tests — file backend, fully offline.
The Supabase backends implement the same interface against Postgres."""

import json

from paper_trail.repositories.cache import (
    FilePageStore,
    FileVectorIndex,
    content_key,
    pad_vector,
    url_key,
)
from paper_trail.sources.fetch import FetchedPage

PAGE = FetchedPage(url="https://rev8.hu/utcafasitas/", title="Utcafásítás",
                   text="fák és zöldfelületek " * 100)
VECTORS = [("chunk a", [1.0, 0.0]), ("chunk b", [0.0, 1.0])]


def test_page_store_roundtrip(tmp_path):
    store = FilePageStore(tmp_path / "fetched")
    assert store.get(PAGE.url) is None
    store.put(PAGE)
    got = store.get(PAGE.url)
    assert got is not None
    assert (got.url, got.title, got.text) == (PAGE.url, PAGE.title, PAGE.text)


def test_vector_index_roundtrip_and_match(tmp_path):
    index = FileVectorIndex(tmp_path / "fetched")
    assert index.get(PAGE, "hashing", 2400) is None
    assert not index.has(PAGE, "hashing", 2400)
    index.put(PAGE, "hashing", 2400, VECTORS)
    assert index.get(PAGE, "hashing", 2400) == VECTORS
    assert index.has(PAGE, "hashing", 2400)
    # a different model or a changed document must miss the cache
    assert index.get(PAGE, "other-model", 2400) is None
    changed = FetchedPage(PAGE.url, PAGE.title, PAGE.text + " changed")
    assert index.get(changed, "hashing", 2400) is None

    top = index.match([1.0, 0.0], "hashing", 2400, [PAGE], k=1)
    assert len(top) == 1 and top[0][1] == "chunk a"


def test_pad_vector_is_cosine_neutral():
    a, b = [1.0, 2.0], [2.0, 1.0]
    from paper_trail.ml.embeddings import cosine
    assert cosine(pad_vector(a), pad_vector(b)) == cosine(a, b)
    assert len(pad_vector([1.0])) == 1024


def test_content_and_url_keys_stable():
    assert url_key(PAGE.url) == url_key(PAGE.url)
    assert content_key("m", 2400, "t") != content_key("m", 2400, "t2")


def test_file_layout_compatible_with_legacy_cache(tmp_path):
    """A page written through the store is readable in the old layout —
    tests and caches predating the store must keep working."""
    cache = tmp_path / "fetched"
    FilePageStore(cache).put(PAGE)
    key = url_key(PAGE.url)
    assert (cache / f"{key}.txt").read_text() == PAGE.text
    meta = json.loads((cache / f"{key}.json").read_text())
    assert meta["title"] == PAGE.title
