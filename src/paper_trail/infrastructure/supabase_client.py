"""supabase client factory, use this instead of `create_client` for the shared http settings

* keepalive_expiry=30s: azure snat silently kills idle sockets, a dead pooled one stalls
  until tcp timeout
* explicit timeouts: postgrest defaults to 120s, fail fast so the job poller recovers
* httpx-retries on transport flakes (ReadError, RemoteProtocolError, ConnectError,
  ConnectTimeout), safe because every write is idempotent (upserts, get-or-create, cas claims).
  ReadTimeout is left out on purpose so slow queries aren't duplicated
"""

from __future__ import annotations

import httpx
from httpx_retries import Retry, RetryTransport

from supabase import Client, ClientOptions, create_client

TRANSIENT = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)

RETRY = Retry(
    total=2,
    retry_on_exceptions=TRANSIENT,
    backoff_factor=0.3,
    respect_retry_after_header=False,
)


def create(url: str, key: str) -> Client:
    http = httpx.Client(
        transport=RetryTransport(
            transport=httpx.HTTPTransport(
                limits=httpx.Limits(keepalive_expiry=30.0)),
            retry=RETRY,
        ),
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=10.0),
    )
    return create_client(url, key, options=ClientOptions(httpx_client=http))
