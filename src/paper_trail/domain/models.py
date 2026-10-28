"""domain model, small on purpose

candidates/evidence come out of the pipeline and always carry provenance,
commitments only exist once a human accepts a candidate
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
    """an ingested official document"""

    id: int | None = None
    title: str
    publisher: str
    url: str = ""


class OfficialSource(BaseModel):
    """known official page the evidence search always checks (`official_sources` table)"""

    id: int | None = None
    url: str
    title: str = ""
    publisher: str = ""
    sort_order: int = 0


class DocumentPage(BaseModel):
    page_number: int  # 1-based
    text: str


class PolicyCandidate(BaseModel):
    """possible commitment pulled from the pdf

    invariant: always has a page number + verbatim excerpt
    """

    id: int | None = None
    document_id: int
    suggested_type: CandidateType = CandidateType.UNCLEAR
    text: str = Field(min_length=1)
    normalized_title: str = Field(min_length=1)
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=1)
    code: str | None = None  # e.g. "A1.1.1"
    excerpt_on_page: bool | None = None
    # extracted metadata, rules only
    responsible_org: str | None = None
    timeframe: str | None = None
    deadline_year: int | None = None
    unit: str | None = None
    target_value: float | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class Commitment(BaseModel):
    """accepted objective/measure/target, `parent_id` is the only hierarchy"""

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


class EvidenceItem(BaseModel):
    """passage from an allow-listed official source"""

    id: int | None = None
    commitment_id: int
    url: str
    title: str
    publisher: str = ""
    published_on: date | None = None
    snippet: str = ""  # passage used for ranking
    # rule-based extraction over the source text
    organisations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates_mentioned: list[str] = Field(default_factory=list)
    status_hint: Status = Status.UNKNOWN
    status_excerpt: str | None = None


class MatchFeatures(BaseModel):
    """what went into a suggested link"""

    semantic_similarity: float = 0.0
    shared_organisations: list[str] = Field(default_factory=list)
    shared_locations: list[str] = Field(default_factory=list)
    shared_dates: list[str] = Field(default_factory=list)


class EvidenceLink(BaseModel):
    """proposed commitment <-> evidence link, pending review"""

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
    """money figure found verbatim in a source, raw wording kept, kind never guessed"""

    id: int | None = None
    evidence_id: int
    kind: BudgetKind
    amount_huf: int | None = None
    amount_raw: str = ""
    fiscal_year: int | None = None
    description: str = ""
    source_url: str = ""
