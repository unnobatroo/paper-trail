"""passage-level language analysis, heavy models only load when picked"""
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class Analysis:
    lemmas: list[str] = field(default_factory=list)
    organisations: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


class HuSpacyAnalyzer:
    def __init__(self, model: str = "hu_core_news_lg"):
        self._model = model
        self._nlp = None
        self._lock = Lock()

    def analyze(self, passage: str) -> Analysis:
        if self._nlp is None:
            with self._lock:
                if self._nlp is None:
                    import spacy
                    self._nlp = spacy.load(self._model)
        doc = self._nlp(passage)
        return Analysis(
            lemmas=[t.lemma_.lower() for t in doc if not t.is_space and not t.is_punct],
            organisations=list(dict.fromkeys(e.text for e in doc.ents if e.label_ == "ORG")),
            locations=list(dict.fromkeys(e.text for e in doc.ents if e.label_ in {"LOC", "GPE"})),
            dates=list(dict.fromkeys(e.text for e in doc.ents if e.label_ == "DATE")),
        )
