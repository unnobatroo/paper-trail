"""who, where and when a passage talks about

gliner (multilingual zero-shot ner, apache-2.0, cpu, extra 'ner'). NER=none skips the model
and only keeps bare years, that's what tests and dev boxes run
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .entities import years

GLINER_MODEL = "urchade/gliner_multi-v2.1"
# label we ask gliner for -> our bucket
_LABELS = {"organization": "orgs", "street, square or park": "places", "date": "dates"}


@dataclass
class Found:
    orgs: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


CHUNK_CHARS = 1000


def _chunks(text: str, size: int) -> list[str]:
    # split on whitespace so a name doesn't get cut in half
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + len(word) + 1 > size:
            out.append(cur)
            cur = ""
        cur = f"{cur} {word}" if cur else word
    return out + [cur] if cur else out


def _dedupe(names: list[str]) -> list[str]:
    return list({n.lower(): n for n in reversed(names)}.values())[::-1]


class NoNer:
    def find(self, text: str) -> Found:
        return Found(dates=years(text))


class GlinerNer:
    def __init__(self, model: str = GLINER_MODEL, threshold: float = 0.4,
                 cache_dir: str | None = None):
        self._name, self._threshold, self._cache = model, threshold, cache_dir
        self._loaded, self._lock = None, threading.Lock()

    @property
    def _model(self):
        # loaded on first use, it's ~1 gb and the api process never needs it.
        # locked: job workers share this and two parallel loads = 2 gb spike
        with self._lock:
            if self._loaded is None:
                try:
                    from gliner import GLiNER
                except ImportError as exc:
                    raise RuntimeError(
                        "NER=gliner needs `uv sync --extra ner` (or set NER=none)") from exc
                self._loaded = GLiNER.from_pretrained(self._name, cache_dir=self._cache)
            return self._loaded

    def find(self, text: str) -> Found:
        found = Found()
        # gliner only reads ~384 tokens per call, so feed it short chunks, not one cut-off blob
        chunks = _chunks(text, CHUNK_CHARS)
        for ents in (self._model.inference(chunks, list(_LABELS), threshold=self._threshold)
                     if chunks else []):
            for e in ents:
                getattr(found, _LABELS[e["label"]]).append(e["text"].strip())
        # gliner gives "2024. március 15-én", matching wants "2024"
        found.dates += years(text)
        return Found(*map(_dedupe, (found.orgs, found.places, found.dates)))


def get_ner(kind: str, cache_dir: str | None = None) -> GlinerNer | NoNer:
    return GlinerNer(cache_dir=cache_dir) if kind == "gliner" else NoNer()
