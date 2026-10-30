"""request/response shapes. domain models serialize themselves, this is bodies + joined views"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..domain.enums import BudgetKind, CandidateType, Jurisdiction, RelationshipType, Status
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


class GlossaryTerm(DomainModel):
    term: str
    meaning: str


class TrailRowView(DomainModel):
    commitment: Commitment
    evidence: list[EvidenceItem]
    relationships: list[RelationshipType]
    budgets: list[BudgetRecord]
    status: Status
    status_excerpt: str | None
    gaps: list[str]
    financial_states: list[BudgetKind]
    financially_executed: bool
    findings: list[str]

    @classmethod
    def from_row(cls, row: TrailRow) -> TrailRowView:
        return cls(
            commitment=row.commitment,
            evidence=row.evidence,
            relationships=row.relationships,
            budgets=row.budgets,
            status=row.status,
            status_excerpt=row.status_excerpt,
            gaps=row.gaps,
            financial_states=row.financial_states,
            financially_executed=row.financially_executed,
            findings=row.findings,
        )


class TranslateRequest(BaseModel):
    # public endpoint, so bounded: a page of ui strings, not a free translator
    texts: list[Annotated[str, StringConstraints(max_length=4000)]] = Field(max_length=50)


class MetaOut(DomainModel):
    """what this deployment runs"""
    deployment: str
    storage: Literal["postgres", "sqlite"]
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
