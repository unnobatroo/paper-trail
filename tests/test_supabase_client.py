"""Retry behaviour of the hardened Supabase httpx client."""

import httpx
import pytest

from paper_trail.infrastructure.supabase_client import _BACKOFF, _RetryingClient


def _client(handler) -> _RetryingClient:
    c = _RetryingClient(transport=httpx.MockTransport(handler))
    return c


def test_retries_transient_transport_errors(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError("dns flake", request=request)
        return httpx.Response(200, json={"ok": True})

    resp = _client(handler).get("https://x.test/rest/v1/t")
    assert resp.status_code == 200
    assert len(calls) == 3


def test_gives_up_after_backoff_budget(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadError("eagain", request=request)

    with pytest.raises(httpx.ReadError):
        _client(handler).get("https://x.test/rest/v1/t")
    assert len(calls) == len(_BACKOFF) + 1


def test_non_transient_errors_not_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow query", request=request)

    with pytest.raises(httpx.ReadTimeout):
        _client(handler).get("https://x.test/rest/v1/t")
    assert len(calls) == 1


def test_http_errors_not_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"message": "denied"})

    resp = _client(handler).get("https://x.test/rest/v1/t")
    assert resp.status_code == 401
    assert len(calls) == 1
