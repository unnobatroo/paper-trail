"""Retry behaviour of the hardened Supabase httpx client."""

import httpx
import pytest
from httpx_retries import RetryTransport

from paper_trail.infrastructure.supabase_client import RETRY


def _client(handler) -> httpx.Client:
    return httpx.Client(
        transport=RetryTransport(
            transport=httpx.MockTransport(handler), retry=RETRY))


def test_retries_transient_transport_errors():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError("dns flake", request=request)
        return httpx.Response(200, json={"ok": True})

    resp = _client(handler).get("https://x.test/rest/v1/t")
    assert resp.status_code == 200
    assert len(calls) == 3


def test_gives_up_after_retry_budget():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadError("eagain", request=request)

    with pytest.raises(httpx.ReadError):
        _client(handler).get("https://x.test/rest/v1/t")
    assert len(calls) == RETRY.total + 1


def test_non_transient_errors_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow query", request=request)

    with pytest.raises(httpx.ReadTimeout):
        _client(handler).get("https://x.test/rest/v1/t")
    assert len(calls) == 1


def test_http_errors_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500)

    resp = _client(handler).get("https://x.test/rest/v1/t")
    assert resp.status_code == 500
    assert len(calls) == 1
