"""Request/response shapes for the REST API.

Domain objects (PolicyCandidate, Commitment, EvidenceLink, …) are already
pydantic models and serialize directly — these are only the extra shapes:
request bodies, the link+evidence joined view, and the trail row.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain.enums import CandidateType, RelationshipType
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
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


class LinkDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    relationship: RelationshipType | None = None


class BulkLinksRequest(BaseModel):
    accept: list[int] = Field(default_factory=list)
    relationships: dict[int, RelationshipType] = Field(default_factory=dict)
    reject: list[int] = Field(default_factory=list)


class LinkView(BaseModel):
    """A proposed link plus everything needed to review it in one shot."""
    link: EvidenceLink
    evidence: EvidenceItem | None = None
    budgets: list[BudgetRecord] = Field(default_factory=list)


class TrailRowView(BaseModel):
    commitment: Commitment
    evidence: list[EvidenceItem]
    relationships: list[RelationshipType]
    budgets: list[BudgetRecord]
    status: str
    status_excerpt: str | None
    gaps: list[str]

    @classmethod
    def from_row(cls, row: TrailRow) -> "TrailRowView":
        return cls(
            commitment=row.commitment,
            evidence=row.evidence,
            relationships=row.relationships,
            budgets=row.budgets,
            status=row.status.value,
            status_excerpt=row.status_excerpt,
            gaps=row.gaps,
        )


class TranslateRequest(BaseModel):
    texts: list[str]


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: str
    result: object | None = None
    error: str | None = None
    created_at: str
