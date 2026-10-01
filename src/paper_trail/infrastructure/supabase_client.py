"""Shared Supabase client factory.

Every Supabase-backed component calls this instead of `create_client`
directly so they share the same hardened HTTP settings:

* `keepalive_expiry=30s` — cloud NATs (Azure SNAT in particular) drop
  idle outbound connections after a few minutes. A pooled keep-alive
  socket that has been silently killed stalls until TCP timeout on
  reuse. Expiring pooled connections early means requests nearly always
  open a fresh, healthy socket.
* explicit timeouts — the default PostgREST timeout is 120s; a dead
  connection should fail fast so callers (e.g. the job poller, which
  retries every 2s) recover instead of pinning a worker thread for
  two minutes.
"""

from __future__ import annotations

import time

import httpx
from supabase import Client, ClientOptions, create_client

# Transport-level flakes seen on Azure F1: SNAT kills sockets mid-request
# (ReadError EAGAIN, RemoteProtocolError), DNS hiccups (ConnectError),
# TLS handshakes that never finish (ConnectTimeout). All our writes are
# idempotent — upserts, get-or-create, CAS job claims — so replaying a
# request the server may have half-received cannot double-write.
# ReadTimeout is deliberately absent: a slow-but-alive query shouldn't be
# duplicated under load.
_TRANSIENT = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)
_BACKOFF = (0.3, 1.0)


class _RetryingClient(httpx.Client):
    def send(self, request, **kwargs):
        for delay in (*_BACKOFF, None):
            try:
                return super().send(request, **kwargs)
            except _TRANSIENT:
                if delay is None:
                    raise
                time.sleep(delay)


def create(url: str, key: str) -> Client:
    http = _RetryingClient(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=10.0),
        limits=httpx.Limits(keepalive_expiry=30.0),
    )
    return create_client(url, key, options=ClientOptions(httpx_client=http))
