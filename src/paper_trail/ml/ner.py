"""who, where and when a passage talks about

gliner (multilingual zero-shot ner, apache-2.0, cpu) in production. the profile's regex
rules are the offline fallback for tests and dev boxes without the model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from . import entities
from .lang import LanguageProfile

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


class RuleNer:
    def __init__(self, profile: LanguageProfile):
        self._profile = profile

    def find(self, text: str) -> Found:
        return Found(orgs=entities.extract_organisations(text, self._profile),
                     places=entities.extract_locations(text, self._profile),
                     dates=entities.extract_dates(text, self._profile))


class GlinerNer:
    def __init__(self, model: str = GLINER_MODEL, threshold: float = 0.4,
                 cache_dir: str | None = None):
        self._name, self._threshold, self._cache = model, threshold, cache_dir

    @cached_property
    def _model(self):
        # loaded on first use, it's ~1 gb and the api process never needs it
        from gliner import GLiNER
        return GLiNER.from_pretrained(self._name, cache_dir=self._cache)

    def find(self, text: str) -> Found:
        found = Found()
        for e in self._model.predict_entities(text[:4000], list(_LABELS),
                                              threshold=self._threshold):
            getattr(found, _LABELS[e["label"]]).append(e["text"].strip())
        return Found(*map(_dedupe, (found.orgs, found.places, found.dates)))


def get_ner(kind: str, profile: LanguageProfile, cache_dir: str | None = None):
    return GlinerNer(cache_dir=cache_dir) if kind == "gliner" else RuleNer(profile)
