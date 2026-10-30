"""openai sdk client for any openai-style model server (goethe, vllm, tei, llama.cpp)"""

from __future__ import annotations

import os

import httpx
from openai import OpenAI
from pydantic import BaseModel, ValidationError


def model_client(base_url: str | None, api_key: str | None = None,
                 timeout: float = 120) -> OpenAI:
    if not base_url:
        raise ValueError("model server url is not set")
    # goethe self-signs, MODEL_CA_BUNDLE is its cert. a global
    # REQUESTS_CA_BUNDLE would also break the public cas we fetch sources with
    verify = os.environ.get("MODEL_CA_BUNDLE") or True
    return OpenAI(base_url=base_url, api_key=api_key or "none", timeout=timeout,
                  max_retries=2, http_client=httpx.Client(verify=verify, timeout=timeout))


def ask_json[M: BaseModel](client: OpenAI, model: str, prompt: str, schema: type[M], name: str,
                           max_tokens: int) -> M | None:
    """one json-schema constrained call. None when the reply doesn't fit, http errors raise"""
    resp = client.chat.completions.create(
        model=model, temperature=0, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": {
            "name": name, "strict": True, "schema": schema.model_json_schema()}},
        # hybrid qwen3 thinks the whole budget away and answers nothing otherwise
        extra_body=({"chat_template_kwargs": {"enable_thinking": False}}
                    if "qwen3" in model.lower() else None))
    try:
        return schema.model_validate_json(resp.choices[0].message.content or "")
    except ValidationError:
        return None
