"""Domain model — small on purpose.

Pipeline objects (PolicyCandidate, EvidenceItem) are produced by extraction and
retrieval and always carry provenance. Domain records (Commitment) only exist
after a human accepts a candidate; the tracker only shows accepted links.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .enums import (
    BudgetKind,
    CandidateType,
    RelationshipType,
    ReviewStatus,
    Status,
)


class SourceDocument(BaseModel):
    """An official document Paper Trail ingested."""

    id: int | None = None
    title: str
    publisher: str
    url: str = ""


class DocumentPage(BaseModel):
    page_number: int  # 1-based index within the PDF
    text: str


class PolicyCandidate(BaseModel):
    """A possible policy commitment extracted from the strategy PDF.

    Invariant: no candidate exists without a page number and a verbatim
    excerpt. `excerpt_on_page` is set by deterministic verification.
    """

    id: int | None = None
    document_id: int
    suggested_type: CandidateType = CandidateType.UNCLEAR
    text: str = Field(min_length=1)
    normalized_title: str = Field(min_length=1)
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=1)
    code: str | None = None  # e.g. "A1.1.1" when the document assigns one
    excerpt_on_page: bool | None = None
    # simple extracted metadata (deterministic parsing only)
    responsible_org: str | None = None
    timeframe: str | None = None
    deadline_year: int | None = None
    unit: str | None = None
    target_value: float | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class Commitment(BaseModel):
    """An accepted policy commitment: objective, measure or target.

    `parent_id` lets a target hang under a measure, a measure under an
    objective — the only hierarchy the MVP needs.
    """

    id: int | None = None
    candidate_id: int | None = None
    parent_id: int | None = None
    kind: CandidateType
    title: str
    summary: str = ""
    code: str | None = None
    responsible_org: str | None = None
    timeframe: str | None = None
    deadline_year: int | None = None
    unit: str | None = None
    target_value: float | None = None
    source_page: int | None = None

    @property
    def is_measurable(self) -> bool:
        return self.target_value is not None and self.unit is not None


class EvidenceItem(BaseModel):
    """A passage retrieved from an allow-listed official source."""

    id: int | None = None
    commitment_id: int
    url: str
    title: str
    publisher: str = ""
    published_on: date | None = None
    snippet: str = ""  # the passage used for ranking
    # deterministic extraction over the source text
    organisations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates_mentioned: list[str] = Field(default_factory=list)
    status_hint: Status = Status.UNKNOWN
    status_excerpt: str | None = None


class MatchFeatures(BaseModel):
    """The inspectable components behind a suggested link."""

    semantic_similarity: float = 0.0
    shared_organisations: list[str] = Field(default_factory=list)
    shared_locations: list[str] = Field(default_factory=list)
    shared_dates: list[str] = Field(default_factory=list)


class EvidenceLink(BaseModel):
    """A proposed commitment ↔ evidence relationship, pending review."""

    id: int | None = None
    commitment_id: int
    evidence_id: int
    features: MatchFeatures = Field(default_factory=MatchFeatures)
    score: float = 0.0
    suggested_relationship: RelationshipType = RelationshipType.INDIRECT
    reasons: list[str] = Field(default_factory=list)
    relationship: RelationshipType | None = None  # set on review
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class BudgetRecord(BaseModel):
    """One monetary figure found verbatim in an official source.

    `kind` distinguishes estimate / allocation / expenditure; the raw wording
    is always kept. Missing kinds are never estimated.
    """

    id: int | None = None
    evidence_id: int
    kind: BudgetKind
    amount_huf: int | None = None
    amount_raw: str = ""
    fiscal_year: int | None = None
    description: str = ""
    source_url: str = ""
