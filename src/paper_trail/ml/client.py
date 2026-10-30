"""openai sdk client for any openai-style model server (goethe, vllm, tei, llama.cpp)"""

from __future__ import annotations

import os

import httpx
from openai import OpenAI


def model_client(base_url: str | None, api_key: str | None = None,
                 timeout: float = 120) -> OpenAI:
    if not base_url:
        raise ValueError("model server url is not set")
    # goethe self-signs, PAPER_TRAIL_MODEL_CA_BUNDLE is its cert. a global
    # REQUESTS_CA_BUNDLE would also break the public cas we fetch sources with
    verify = os.environ.get("PAPER_TRAIL_MODEL_CA_BUNDLE") or True
    return OpenAI(base_url=base_url, api_key=api_key or "none", timeout=timeout,
                  max_retries=2, http_client=httpx.Client(verify=verify, timeout=timeout))
