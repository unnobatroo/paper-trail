"""edges that used to be soft: allowlist parsing, store paths, request bounds, reranker outages"""

import pytest
from pydantic import ValidationError

from paper_trail.api.schemas import TranslateRequest
from paper_trail.sources.document_store import DocumentStore
from paper_trail.sources.web_search import allowed

DOMAINS = ["jozsefvaros.hu"]


@pytest.mark.parametrize("url, ok", [
    ("https://jozsefvaros.hu/a", True),
    ("https://www.jozsefvaros.hu/a", True),
    ("https://jozsefvaros.hu:443/a", True),
    ("https://jozsefvaros.hu@evil.test/a", False),
    ("https://evil.test/?jozsefvaros.hu", False),
    ("https://notjozsefvaros.hu/a", False),
])
def test_allowlist_uses_the_real_hostname(url, ok):
    assert allowed(url, DOMAINS) is ok


def test_local_store_refuses_paths_outside_its_root(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.pdf").write_bytes(b"%PDF")
    store = DocumentStore(tmp_path / "docs")
    assert store.read("plan.pdf") == b"%PDF"
    with pytest.raises(ValueError):
        store.read("../secrets.env")


def test_translate_request_is_bounded():
    TranslateRequest(texts=["szia"] * 50)
    with pytest.raises(ValidationError):
        TranslateRequest(texts=["szia"] * 51)
    with pytest.raises(ValidationError):
        TranslateRequest(texts=["x" * 4001])
