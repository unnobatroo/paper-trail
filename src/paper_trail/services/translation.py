"""source language -> english machine translation

sources stay verbatim, the ui shows this underneath, labelled as machine translated.
opus-mt-<lang>-en on the hf inference api, no HF_TOKEN = no translation
"""

from __future__ import annotations

from ..ml.lang import LanguageProfile

MT_DISCLAIMER = (
    "English text below is automatic machine translation ({model}) — "
    "for orientation only, not an official document."
)


class Translator:
    def __init__(self, profile: LanguageProfile, api_key: str, model: str | None = None):
        from huggingface_hub import InferenceClient

        self.model = (model
                      or f"Helsinki-NLP/opus-mt-{profile.code}-en")
        self.disclaimer = MT_DISCLAIMER.format(model=self.model)
        self._client = InferenceClient(
            api_key=api_key,
            timeout=60,
        )

    def translate(self, text: str) -> str | None:
        """english, or None if the service is down (ui shows the source)"""
        if not text.strip():
            return None
        try:
            out = self._client.translation(
                text[:4000], model=self.model)
            return out.translation_text if out else None
        except Exception:
            return None


def get_translator(profile: LanguageProfile, token: str | None, model: str | None = None,
                   *, enabled: bool = True) -> Translator | None:
    """translator if there's an HF_TOKEN, else None"""
    if not enabled or not token:
        return None
    return Translator(profile, token, model)
