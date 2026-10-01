"""Source-language → English machine translation at runtime.

The source documents are verbatim for provenance; the UI shows an optional
machine translation underneath for orientation. Everything this module
produces is labelled automatic translation — it is never presented as an
official document.

Backend: a Helsinki-NLP opus-mt-*-en model on the Hugging Face Inference
API. Needs HF_TOKEN; without one the UI simply shows no translation.
The model defaults to opus-mt-<PAPER_TRAIL_LANGUAGE>-en and can be
overridden with PAPER_TRAIL_MT_MODEL.
"""

from __future__ import annotations

import os

from ..ml.lang import LanguageProfile

MT_DISCLAIMER = (
    "English text below is automatic machine translation ({model}) — "
    "for orientation only, not an official document."
)


class Translator:
    def __init__(self, profile: LanguageProfile, api_key: str | None = None,
                 model: str | None = None):
        from huggingface_hub import InferenceClient

        self.model = (model
                      or f"Helsinki-NLP/opus-mt-{profile.code}-en")
        self.disclaimer = MT_DISCLAIMER.format(model=self.model)
        self._client = InferenceClient(
            api_key=api_key or os.environ.get("HF_TOKEN", ""),
            timeout=60,
        )

    def translate(self, text: str) -> str | None:
        """English rendering of `text`, or None when the service is
        unavailable — the caller falls back to the source language."""
        if not text.strip():
            return None
        try:
            out = self._client.translation(
                text[:4000], model=self.model)
            return out.translation_text if out else None
        except Exception:
            return None


def get_translator(profile: LanguageProfile,
                   model: str | None = None) -> Translator | None:
    """A translator when HF_TOKEN is configured, else None."""
    if not os.environ.get("HF_TOKEN"):
        return None
    return Translator(profile, model=model)
