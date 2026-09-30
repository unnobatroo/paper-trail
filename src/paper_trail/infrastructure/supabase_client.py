"""Shared Supabase client factory.

Every Supabase-backed component calls this instead of `create_client`
directly so they share the same hardened HTTP settings:

* `keep_alive_expiry=30s` — cloud NATs (Azure SNAT in particular) drop
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

import httpx
from supabase import Client, ClientOptions, create_client


def create(url: str, key: str) -> Client:
    http = httpx.Client(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=10.0),
        limits=httpx.Limits(keep_alive_expiry=30.0),
    )
    return create_client(url, key, options=ClientOptions(httpx_client=http))
