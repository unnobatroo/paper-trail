import pytest

from paper_trail.ml import embeddings
from paper_trail.ml.embeddings import OpenAICompatEmbeddingProvider, get_provider


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def _stub(monkeypatch, calls, shuffle=True):
    def post(url, headers, json, timeout):
        calls.append((url, json))
        idx = list(range(len(json["input"])))
        if shuffle:
            idx.reverse()
        # vector value encodes the input text so order mistakes are visible
        return _Resp({"data": [
            {"index": i, "embedding": [float(len(json["input"][i])), 0.0]} for i in idx]})

    monkeypatch.setattr(embeddings.requests, "post", post)


def test_batches_and_keeps_input_order(monkeypatch):
    calls = []
    _stub(monkeypatch, calls)
    p = OpenAICompatEmbeddingProvider("http://x/v1/", batch_size=2)
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    vecs = p.embed(texts)
    assert [v[0] for v in vecs] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [len(c[1]["input"]) for c in calls] == [2, 2, 1]
    assert calls[0][0] == "http://x/v1/embeddings"


def test_model_name_is_prefixed():
    assert OpenAICompatEmbeddingProvider("http://x/v1").model_name == "openai:bge-m3"


def test_duplicate_or_missing_indices_raise(monkeypatch):
    # full-length reply, but index 0 twice and 1 missing: would silently misalign vectors
    monkeypatch.setattr(
        embeddings.requests, "post",
        lambda *a, **k: _Resp({"data": [
            {"index": 0, "embedding": [1.0]}, {"index": 0, "embedding": [2.0]}]}))
    with pytest.raises(ValueError):
        OpenAICompatEmbeddingProvider("http://x/v1").embed(["a", "b"])


def test_api_key_is_sent_as_bearer(monkeypatch):
    seen = {}

    def post(url, headers, json, timeout):
        seen.update(headers)
        return _Resp({"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setattr(embeddings.requests, "post", post)
    get_provider("bge-m3", base_url="http://x/v1", api_key="s3cret").embed(["a"])
    assert seen["Authorization"] == "Bearer s3cret"


def test_count_mismatch_raises(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post",
        lambda *a, **k: _Resp({"data": [{"index": 0, "embedding": [1.0]}]}))
    with pytest.raises(ValueError):
        OpenAICompatEmbeddingProvider("http://x/v1").embed(["a", "b"])


@pytest.mark.parametrize("name", ["bge-m3", "openai:bge-m3"])
def test_get_provider_selects_openai_compat(name):
    p = get_provider(name, base_url="http://x/v1")
    assert isinstance(p, OpenAICompatEmbeddingProvider)
    assert p.model_name == "openai:bge-m3"


def test_missing_base_url_is_an_error(monkeypatch):
    monkeypatch.delenv("PAPER_TRAIL_EMBED_BASE_URL", raising=False)
    with pytest.raises(ValueError):
        get_provider("bge-m3")
