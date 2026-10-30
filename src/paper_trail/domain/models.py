"""domain model, small on purpose. candidates/evidence always carry receipts,
commitments only exist once a person accepts one
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ArtifactStatus,
    BudgetKind,
    CandidateType,
    EvidenceFlag,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
    Status,
)


class DomainModel(BaseModel):
    """base for everything the api returns

    defaulted fields are always sent, so mark them required in the schema,
    otherwise the generated ts types (web/src/lib/api-schema.ts) lie
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class SourceDocument(DomainModel):
    """an ingested official document"""

    id: int | None = None
    title: str
    publisher: str
    url: str = ""


class OfficialSource(DomainModel):
    """official page the search always checks (official_sources table)"""

    id: int | None = None
    url: str
    title: str = ""
    publisher: str = ""
    sort_order: int = 0
    # whose asset this source covers, None = searched for everything
    jurisdiction: Jurisdiction | None = None


class DocumentPage(DomainModel):
    page_number: int  # 1-based
    text: str


class PolicyCandidate(DomainModel):
    """maybe-commitment from the pdf. always has a page + verbatim excerpt"""

    id: int | None = None
    document_id: int
    suggested_type: CandidateType = CandidateType.UNCLEAR
    text: str = Field(min_length=1)
    normalized_title: str = Field(min_length=1)
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=1)
    code: str | None = None  # e.g. "A1.1.1"
    excerpt_on_page: bool | None = None
    # metadata, rules only
    responsible_org: str | None = None
    timeframe: str | None = None
    deadline_year: int | None = None
    unit: str | None = None
    target_value: float | None = None
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class Commitment(DomainModel):
    """accepted objective/measure/target, parent_id is the whole hierarchy"""

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
    # guessed from the wording on accept, reviewer can change it
    asset_owner_jurisdiction: Jurisdiction = Jurisdiction.DISTRICT_MUNICIPALITY


class EvidenceItem(DomainModel):
    """passage from an allowlisted official source"""

    id: int | None = None
    commitment_id: int
    url: str
    title: str
    publisher: str = ""
    published_on: date | None = None
    snippet: str = ""  # passage used for ranking
    # rule-based, from the passage
    organisations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates_mentioned: list[str] = Field(default_factory=list)
    status_hint: Status = Status.UNKNOWN
    status_excerpt: str | None = None
    # all from the matched passage only
    polarity: EvidencePolarity = EvidencePolarity.AFFIRMATIVE
    flags: list[EvidenceFlag] = Field(default_factory=list)
    procurement_ids: list[str] = Field(default_factory=list)  # EKR / EU project codes
    parcels: list[str] = Field(default_factory=list)  # hrsz numbers as written


class ImplementationArtifact(DomainModel):
    """contract/lot/funded project, keyed by its official id

    one umbrella contract for 45 streets = one node every commitment's evidence
    can point at, so a later cancellation hits all of them
    """

    id: int | None = None
    procurement_id: str
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    status_evidence_id: int | None = None  # the passage that amended/terminated it


class MatchFeatures(DomainModel):
    """what went into a suggested link"""

    semantic_similarity: float = 0.0
    shared_organisations: list[str] = Field(default_factory=list)
    shared_locations: list[str] = Field(default_factory=list)
    shared_dates: list[str] = Field(default_factory=list)


class EvidenceLink(DomainModel):
    """suggested commitment <-> evidence link, waiting for a person"""

    id: int | None = None
    commitment_id: int
    evidence_id: int
    features: MatchFeatures = Field(default_factory=MatchFeatures)
    score: float = 0.0
    suggested_relationship: RelationshipType = RelationshipType.INDIRECT
    reasons: list[str] = Field(default_factory=list)
    relationship: RelationshipType | None = None  # set on review
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED


class BudgetRecord(DomainModel):
    """money quoted verbatim, raw wording kept, kind never guessed"""

    id: int | None = None
    evidence_id: int
    kind: BudgetKind
    amount_huf: int | None = None
    currency: str = "HUF"
    amount_native: str | None = None
    amount_raw: str = ""
    fiscal_year: int | None = None
    description: str = ""
    source_url: str = ""
