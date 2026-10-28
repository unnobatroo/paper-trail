"""source language -> english machine translation

sources stay verbatim, the ui shows this underneath labelled as automatic translation.
backend: helsinki-nlp opus-mt-<lang>-en on the hf inference api (needs HF_TOKEN, no token = no
translation), override with PAPER_TRAIL_MT_MODEL
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
        """english text, or None if the service is down (caller shows the source)"""
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
    """translator if HF_TOKEN is set, else None"""
    if not os.environ.get("HF_TOKEN"):
        return None
    return Translator(profile, model=model)
