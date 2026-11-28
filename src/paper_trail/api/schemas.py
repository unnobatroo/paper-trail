"""request/response shapes. domain models serialize themselves, this is bodies + joined views"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..domain.enums import CandidateType, Jurisdiction, RelationshipType
from ..domain.models import (
    BudgetRecord,
    Commitment,
    DomainModel,
    EvidenceItem,
    EvidenceLink,
    Note,
    PolicyCandidate,
)
from ..services.metrics_service import TrailRow


class IngestRequest(BaseModel):
    name: str = Field(description="filename in the document store")
    title: str
    publisher: str
    url: str = ""


class AcceptCandidateRequest(BaseModel):
    kind: CandidateType | None = None
    title: str | None = None
    parent_id: int | None = None


class BulkCandidatesRequest(BaseModel):
    accept: list[int] = Field(default_factory=list)
    reject: list[int] = Field(default_factory=list)
    reject_rest: bool = False


class JurisdictionRequest(BaseModel):
    jurisdiction: Jurisdiction


class LinkDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    relationship: RelationshipType | None = None


class BulkLinksRequest(BaseModel):
    accept: list[int] = Field(default_factory=list)
    relationships: dict[int, RelationshipType] = Field(default_factory=dict)
    reject: list[int] = Field(default_factory=list)


class LinkView(DomainModel):
    """link + everything you need to review it"""
    link: EvidenceLink
    evidence: EvidenceItem | None = None
    budgets: list[BudgetRecord] = Field(default_factory=list)
    note: Note | None = None


class CandidateView(PolicyCandidate):
    """a candidate plus its plain-english note, if someone wrote one"""
    note: Note | None = None


class HighlightBox(DomainModel):
    """a rectangle on the page, as fractions of its width and height from the top left"""
    x: float
    y: float
    w: float
    h: float


class PageHighlight(DomainModel):
    """where a candidate's quote sits on its source page, and where to get the page as an image"""
    page: int
    found: bool  # false when the page's own text doesn't contain the quote
    boxes: list[HighlightBox]
    image_url: str


class GlossaryTerm(DomainModel):
    term: str
    meaning: str


class TranslateRequest(BaseModel):
    # public endpoint, so bounded: a page of ui strings, not a free translator
    texts: list[Annotated[str, StringConstraints(max_length=4000)]] = Field(max_length=50)


class MetaOut(DomainModel):
    """what this deployment runs"""
    deployment: str
    storage: Literal["postgres"]
    embed_model: str
    reranker: str
    search_provider: str
    llm_extraction: bool
    review_required: bool  # mutations need X-Review-Key
    translation: bool
    # false until `maintenance profile import`, the rules find nothing without one
    language_profile_loaded: bool
    language_name: str = ""  # "Hungarian", labels the original-language toggle
    # source-language words and codes explained in plain english, from the profile
    glossary: list[GlossaryTerm] = Field(default_factory=list)


class JobOut(DomainModel):
    id: str
    kind: str
    status: str
    progress: str
    result: object | None = None
    error: str | None = None
    created_at: str


class WorkspaceRow(DomainModel):
    """One commitment across the pipeline, as the review workspace shows it."""

    id: int
    title: str
    kind: str
    stage: Literal["confirm", "search", "review", "done", "rejected"]
    group: list[CandidateView]
    commitments: list[Commitment]
    trail: list[TrailRow]
    pending: list[LinkView]
    evidence: int
    searchable: bool


class WorkspaceOut(DomainModel):
    """The rows that pass the filters, plus what the page needs around them."""

    rows: list[WorkspaceRow]
    stage_counts: dict[str, int]
    commitments: list[Commitment]
    documents: dict[int, str]
