"""who, where and when a passage talks about

gliner (multilingual zero-shot ner, apache-2.0, cpu, extra 'ner'). NER=none skips the model
and only keeps bare years, that's what tests and dev boxes run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from .entities import years

GLINER_MODEL = "urchade/gliner_multi-v2.1"
# label we ask gliner for -> our bucket
_LABELS = {"organization": "orgs", "street, square or park": "places", "date": "dates"}


@dataclass
class Found:
    orgs: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


def _dedupe(names: list[str]) -> list[str]:
    return list({n.lower(): n for n in reversed(names)}.values())[::-1]


class NoNer:
    def find(self, text: str) -> Found:
        return Found(dates=years(text))


class GlinerNer:
    def __init__(self, model: str = GLINER_MODEL, threshold: float = 0.4,
                 cache_dir: str | None = None):
        self._name, self._threshold, self._cache = model, threshold, cache_dir

    @cached_property
    def _model(self):
        # loaded on first use, it's ~1 gb and the api process never needs it
        try:
            from gliner import GLiNER
        except ImportError as exc:
            raise RuntimeError("NER=gliner needs `uv sync --extra ner` (or set NER=none)") from exc
        return GLiNER.from_pretrained(self._name, cache_dir=self._cache)

    def find(self, text: str) -> Found:
        found = Found()
        for e in self._model.predict_entities(text[:4000], list(_LABELS),
                                              threshold=self._threshold):
            getattr(found, _LABELS[e["label"]]).append(e["text"].strip())
        # gliner gives "2024. március 15-én", matching wants "2024"
        found.dates += years(text)
        return Found(*map(_dedupe, (found.orgs, found.places, found.dates)))


def get_ner(kind: str, cache_dir: str | None = None) -> GlinerNer | NoNer:
    return GlinerNer(cache_dir=cache_dir) if kind == "gliner" else NoNer()
