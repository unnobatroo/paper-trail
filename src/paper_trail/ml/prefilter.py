"""page prefilter: skip pages that almost never hold a commitment before the model reads them

A logistic regression over a few counts (measure-sheet field labels, deadlines, costs,
measure codes, figure captions, digit share, length). The model file carries its own
patterns, weights and threshold, so no word lists live here and another language is another
file. Training and serving share `features`, which keeps them from drifting apart.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterator
from pathlib import Path

from ..domain.models import DocumentPage, PolicyCandidate


class PagePrefilter:
    """scores a page's text; `keep` is true for pages the extractor should read"""

    def __init__(self, spec: dict):
        # the name keys ingest checkpoints, so it has to change with anything that changes
        # which pages are kept: a digest of the whole spec, not just its label
        digest = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:8]
        self.name = f"{spec['name']}-{digest}"
        self.threshold = float(spec["threshold"])
        self._fields = [re.compile(p, re.I) for p in spec["fields"]]
        self._counts = [re.compile(p, re.I) for p in spec["counts"].values()]
        self._mean, self._scale = spec["mean"], spec["scale"]
        self._coef, self._bias = spec["coef"], float(spec["intercept"])

    @classmethod
    def load(cls, path: str | Path) -> PagePrefilter:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def features(self, text: str) -> list[float]:
        """field labels present, log(1 + matches) per count pattern, digit share, log length"""
        fields = sum(bool(f.search(text)) for f in self._fields)
        counts = [math.log1p(len(c.findall(text))) for c in self._counts]
        digits = sum(ch.isdigit() for ch in text) / max(len(text), 1)
        return [float(fields), *counts, digits, math.log1p(len(text.split()))]

    def score(self, text: str) -> float:
        z = self._bias + sum(
            w * (x - m) / s
            for w, x, m, s in zip(self._coef, self.features(text), self._mean, self._scale,
                                  strict=True))
        return 1 / (1 + math.exp(-z))

    def keep(self, text: str) -> bool:
        return self.score(text) >= self.threshold


class PrefilteredExtractor:
    """runs the wrapped extractor on kept pages only; skipped pages still come back as
    read-with-nothing-found, so ingest checkpoints them and a retry doesn't score them again"""

    def __init__(self, inner, prefilter: PagePrefilter):
        self._inner = inner
        self._filter = prefilter
        # another filter reads another set of pages, so it needs its own checkpoints
        self.name = f"{inner.name}+{prefilter.name}"

    def extract_windows(self, pages: list[DocumentPage]
                        ) -> Iterator[tuple[list[DocumentPage], list[PolicyCandidate]]]:
        kept, skipped = [], []
        for page in pages:
            (kept if self._filter.keep(page.text) else skipped).append(page)
        for page in skipped:
            yield [page], []
        yield from self._inner.extract_windows(kept)
