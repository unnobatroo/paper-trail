import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from paper_trail.ml.embeddings import HashingProvider, HttpEmbedder, LocalEmbedder, get_provider


def _server(calls, shuffle=True):
    """fake sdk client, vector value = input length so order mixups show"""
    def create(model, input, encoding_format):
        calls.append(input)
        idx = list(range(len(input)))[::-1] if shuffle else list(range(len(input)))
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=[float(len(input[i])), 0.0])
                                     for i in idx])
    return SimpleNamespace(embeddings=SimpleNamespace(create=create))


def test_batches_and_keeps_input_order():
    calls = []
    embedder = HttpEmbedder(_server(calls), "m", batch_size=2)
    vecs = embedder.embed(["a", "bb", "ccc", "dddd", "eeeee"])
    assert [v[0] for v in vecs] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert [len(c) for c in calls] == [2, 2, 1]


def test_model_name_is_prefixed():
    assert HttpEmbedder(_server([]), "Qwen/Qwen3-Embedding-0.6B").model_name == (
        "openai:Qwen/Qwen3-Embedding-0.6B")


def test_bad_indices_raise():
    # index 0 twice, 1 missing: would silently misalign vectors
    rows = [SimpleNamespace(index=0, embedding=[1.0]), SimpleNamespace(index=0, embedding=[2.0])]
    client = SimpleNamespace(embeddings=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(data=rows)))
    with pytest.raises(ValueError):
        HttpEmbedder(client, "m").embed(["a", "b"])


def test_real_sdk_sends_key_path_and_float_encoding():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(url=str(request.url), auth=request.headers["authorization"],
                    body=json.loads(request.content))
        return httpx.Response(200, json={"object": "list", "model": "m", "data": [
            {"object": "embedding", "index": 0, "embedding": [0.5, 0.25]}]})
    client = OpenAI(base_url="https://goethe:8443/v1", api_key="s3cret",
                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert HttpEmbedder(client, "m").embed(["a"]) == [[0.5, 0.25]]
    assert seen["url"] == "https://goethe:8443/v1/embeddings"
    assert seen["auth"] == "Bearer s3cret"
    assert seen["body"]["encoding_format"] == "float"


def test_get_provider_picks_by_name():
    assert isinstance(get_provider("hashing"), HashingProvider)
    assert isinstance(get_provider("openai:m", base_url="http://x/v1"), HttpEmbedder)
    assert isinstance(get_provider("some/fastembed-model"), LocalEmbedder)
    with pytest.raises(ValueError):
        get_provider("openai:m")  # no server url
