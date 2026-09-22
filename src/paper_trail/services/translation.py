"""Hungarian → English machine translation at runtime.

The source documents are Hungarian; the UI keeps them verbatim for
provenance and shows an optional machine translation underneath for
orientation. Everything this module produces is labelled automatic
translation — it is never presented as an official document.

Backend: Helsinki-NLP/opus-mt-hu-en on the Hugging Face Inference API.
Needs HF_TOKEN; without one the UI simply shows no translation.
"""

from __future__ import annotations

import os

import requests

MT_MODEL = "Helsinki-NLP/opus-mt-hu-en"
MT_DISCLAIMER = (
    "English text below is automatic machine translation "
    f"({MT_MODEL}) — for orientation only, not an official document."
)

_ENDPOINT = "https://router.huggingface.co/hf-inference/models/"


class Translator:
    def __init__(self, api_key: str | None = None, model: str = MT_MODEL):
        self.model = model
        self._key = api_key or os.environ.get("HF_TOKEN", "")
        self._url = _ENDPOINT + model

    def translate(self, text: str) -> str | None:
        """English rendering of `text`, or None when the service is
        unavailable — the caller falls back to Hungarian only."""
        if not text.strip():
            return None
        try:
            resp = requests.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={"inputs": text[:4000]},
                timeout=60,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("translation_text")
            return data.get("translation_text") if isinstance(data, dict) else None
        except requests.RequestException:
            return None


def get_translator() -> Translator | None:
    """A translator when HF_TOKEN is configured, else None."""
    return Translator() if os.environ.get("HF_TOKEN") else None
