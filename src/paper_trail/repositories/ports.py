"""what services need from storage, postgres/ + store.py implement it,
services never touch a concrete backend
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from ..domain.enums import (
    CandidateType,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
)
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    ImplementationArtifact,
    Note,
    OfficialSource,
    PolicyCandidate,
    SourceDocument,
)
from ..sources.fetch import FetchedPage


class PolicyStore(Protocol):
    """documents, candidates, commitments"""

    def add_document(self, doc: SourceDocument) -> int: ...

    def documents(self) -> list[SourceDocument]: ...

    def add_candidate(self, cand: PolicyCandidate) -> int: ...

    def candidates(self, status: ReviewStatus | None = None) -> list[PolicyCandidate]: ...

    def candidate(self, candidate_id: int) -> PolicyCandidate | None: ...

    def set_candidate_status(self, candidate_id: int, status: ReviewStatus) -> None: ...

    def add_commitment(self, com: Commitment) -> int: ...

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]: ...

    def commitment(self, commitment_id: int) -> Commitment | None: ...

    def set_commitment_jurisdiction(self, commitment_id: int,
                                    jurisdiction: Jurisdiction) -> None: ...

    # language profiles are data: the rules' word lists, one json document per code
    def language_profile(self, code: str) -> dict | None: ...

    def put_language_profile(self, code: str, profile: dict) -> None: ...

    def notes(self, kind: str, ids: list[int]) -> dict[int, Note]: ...

    def put_note(self, note: Note) -> None: ...


class EvidenceStore(Protocol):
    """official sources, evidence, links, budgets"""

    def official_sources(self) -> list[OfficialSource]: ...

    def upsert_official_source(self, src: OfficialSource) -> None: ...

    def reviewed_evidence_id(self, commitment_id: int, url: str) -> int | None: ...

    def add_evidence(self, ev: EvidenceItem) -> int: ...

    def evidence(self, evidence_id: int) -> EvidenceItem | None: ...

    def evidence_many(self, ids: list[int]) -> dict[int, EvidenceItem]: ...

    def add_link(self, link: EvidenceLink) -> int: ...

    def links(self, status: ReviewStatus | None = None) -> list[EvidenceLink]: ...

    def links_for(self, commitment_id: int) -> list[EvidenceLink]: ...

    def link(self, link_id: int) -> EvidenceLink | None: ...

    def decide_link(
            self,
            link_id: int,
            status: ReviewStatus,
            relationship: RelationshipType | None = None,
    ) -> None: ...

    def add_budget(self, b: BudgetRecord) -> int: ...

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]: ...

    def budgets_many(self, evidence_ids: list[int]) -> dict[int, list[BudgetRecord]]: ...

    # artifacts: one contract node shared by every passage naming it
    def link_artifact(self, procurement_id: str, evidence_id: int,
                      polarity: EvidencePolarity) -> ImplementationArtifact | None: ...

    def artifacts_many(self, evidence_ids: list[int]
                       ) -> dict[int, list[ImplementationArtifact]]: ...

    # gazetteer: parcels + known street names
    def resolve_parcel(self, parcel: str) -> str | None: ...

    def record_parcel(self, parcel: str, street: str, source: str) -> None: ...

    def place_names(self) -> list[str]: ...


# page + vector caches: tables + pgvector


class PageStore(ABC):
    """fetch cache, url -> page. fetch once, read forever"""

    @abstractmethod
    def get(self, url: str) -> FetchedPage | None:
        """cached page, None if never fetched"""

    @abstractmethod
    def put(self, page: FetchedPage) -> None:
        """store a page, re-putting a url is a no-op or an upsert"""

    def page_id(self, url: str) -> int | None:
        """row id for chunk storage, file stores don't have one"""
        return None


class VectorIndex(ABC):
    """chunk vectors per page + top-k retrieval"""

    @abstractmethod
    def has(self, page: FetchedPage, model: str, chunk_size: int) -> bool:
        """cheap check, never downloads vectors"""

    @abstractmethod
    def get(self, page: FetchedPage, model: str,
            chunk_size: int) -> list[tuple[str, list[float]]] | None:
        """cached (chunk, vector) pairs for page + model, or None"""

    @abstractmethod
    def put(self, page: FetchedPage, model: str, chunk_size: int,
            pairs: list[tuple[str, list[float]]]) -> None:
        """save chunk vectors for a page under this model"""

    @abstractmethod
    def match(self, query: list[float], query_text: str, model: str,
              chunk_size: int, pages: list[FetchedPage],
              k: int) -> list[tuple[FetchedPage, str, float]]:
        """top-k (page, chunk, score) across pages, best first. dense fused with lexical,
        pages without vectors get skipped
        """
