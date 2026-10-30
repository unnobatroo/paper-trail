"""language profile = every word list and doc label the deterministic rules use

no data in here, profiles live in the db (language_profiles table), managed with
`python -m paper_trail.maintenance profile import FILE`. tests use tests/fixtures/profiles/
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from ..domain.enums import BudgetKind, Jurisdiction, Status


@dataclass(frozen=True)
class LanguageProfile:
    """one language's cue tables, matched against lowercased text"""

    code: str  # ISO-ish tag, e.g. "hu"
    name: str  # "Hungarian" — used in LLM prompts
    stemmer: str  # snowball language name
    ts_config: str  # Postgres regconfig for tsvector columns

    # money
    currency: str = ""  # local ISO code, "HUF"
    # word as written -> ISO code, {"Ft": "HUF", "€": "EUR"}. bare list = all local
    currency_words: dict[str, str] = field(default_factory=dict)
    min_amount: int = 0  # local-currency amounts under this are noise
    multiplier_words: dict[str, int] = field(default_factory=dict)
    decimal_comma: bool = False  # "2,5" = 2.5
    # first kind whose cue is in the sentence wins, so later budget states go first
    budget_cues: dict[BudgetKind, tuple[str, ...]] = field(
        default_factory=dict)
    # signed handover record, proof of done that isn't money
    completion_certificate_cues: tuple[str, ...] = ()

    # passage polarity (zombie tenders)
    termination_cues: tuple[str, ...] = ()
    amendment_cues: tuple[str, ...] = ()

    # additionality: repair talk vs actual upgrade talk
    maintenance_cues: tuple[str, ...] = ()
    upgrade_cues: tuple[str, ...] = ()

    # words that name an asset owner. where the owner publishes is deployment data,
    # that lives in official_sources.jurisdiction
    jurisdiction_cues: dict[Jurisdiction, tuple[str, ...]] = field(default_factory=dict)

    # places come from gliner, this just folds their inflections for matching
    place_drop_suffixes: tuple[str, ...] = ()  # inflections norm_place strips

    # document/report classification
    report_cues: tuple[str, ...] = ()
    status_rules: tuple[tuple[Status, tuple[str, ...]], ...] = ()
    title_stopwords: frozenset[str] = frozenset()

    # tender / eu project ids and land-registry numbers, both per country
    procurement_id_re: str = ""  # EKR\d{9,12}|…
    parcel_re: str = ""  # group 1 or 2 = the number

    # field labels of measure fact sheets ("időtáv", "felelős"). a quote that's mostly these
    # is a form row, not a commitment, the extractor drops it
    form_labels: tuple[str, ...] = ()

    # term as it shows up in documents -> plain-english meaning, for the ui
    glossary: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:  # dict fields aren't hashable, key on code
        return hash(self.code)

    @classmethod
    def empty(cls, code: str = "") -> LanguageProfile:
        """no cues at all: rules find nothing, nothing breaks. what you get before an import"""
        return cls(code=code, name=code or "unknown", stemmer="english", ts_config="simple")

    @classmethod
    def from_dict(cls, data: dict) -> LanguageProfile:
        # unknown keys get skipped, older db profiles still carry the regex ner fields
        kwargs = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if f.name == "budget_cues":
                value = {BudgetKind(k): tuple(v) for k, v in value.items()}
            elif f.name == "jurisdiction_cues":
                value = {Jurisdiction(k): tuple(v) for k, v in value.items()}
            elif f.name == "status_rules":
                value = tuple((Status(s), tuple(cues)) for s, cues in value)
            elif f.name == "title_stopwords":
                value = frozenset(value)
            elif f.name == "currency_words" and isinstance(value, list):
                # old profiles: plain word list, all local currency
                value = {w: data.get("currency", "") for w in value}
            elif isinstance(value, list):
                value = tuple(value)
            kwargs[f.name] = value
        return cls(**kwargs)

    def to_dict(self) -> dict:
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in ("budget_cues", "jurisdiction_cues"):
                value = {k.value: list(v) for k, v in value.items()}
            elif f.name == "status_rules":
                value = [[s.value, list(cues)] for s, cues in value]
            elif f.name == "title_stopwords":
                value = sorted(value)
            elif isinstance(value, tuple):
                value = list(value)
            out[f.name] = value
        return out
