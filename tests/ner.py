"""canned ner for tests, the real one is a 1 gb gliner download"""
from paper_trail.ml.ner import Found, NoNer


class StubNer(NoNer):
    """whichever of these names shows up in the text, plus bare years like the real thing"""

    def __init__(self, orgs=(), places=()):
        self._orgs, self._places = orgs, places

    def find(self, text: str) -> Found:
        return Found(orgs=[o for o in self._orgs if o in text],
                     places=[p for p in self._places if p in text],
                     dates=super().find(text).dates)
