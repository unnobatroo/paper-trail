"""human review, the only road from pipeline output to the trail"""

from __future__ import annotations

from ..domain.enums import CandidateType, Jurisdiction, RelationshipType, ReviewStatus
from ..domain.models import Commitment, PolicyCandidate
from ..ml.accountability import PassageAuditor
from ..ml.lang import LanguageProfile
from ..repositories.ports import EvidenceStore, PolicyStore


class ReviewService:
    def __init__(self, policy: PolicyStore, evidence: EvidenceStore,
                 profile: LanguageProfile | None = None):
        self._policy = policy
        self._evidence = evidence
        self._auditor = PassageAuditor(profile or LanguageProfile.empty())

    def accept_candidate(
            self,
            candidate_id: int,
            kind: CandidateType | None = None,
            title: str | None = None,
            parent_id: int | None = None,
    ) -> int:
        cand = self._policy.candidate(candidate_id)
        if cand is None:
            raise ValueError(f"unknown candidate {candidate_id}")
        if cand.excerpt_on_page is not True or not cand.source_excerpt.strip():
            raise ValueError("candidate has no verified source receipt")
        commitment = Commitment(
            candidate_id=cand.id,
            parent_id=parent_id,
            kind=kind or cand.suggested_type,
            title=title or cand.normalized_title,
            summary=cand.text,
            code=cand.code,
            responsible_org=cand.responsible_org,
            timeframe=cand.timeframe,
            deadline_year=cand.deadline_year,
            unit=cand.unit,
            target_value=cand.target_value,
            source_page=cand.source_page,
            # owner guess from the wording, reviewer can change it
            asset_owner_jurisdiction=self._auditor.jurisdiction(
                f"{title or cand.normalized_title} {cand.text}"),
        )
        cid = self._policy.add_commitment(commitment)
        self._policy.set_candidate_status(candidate_id, ReviewStatus.ACCEPTED)
        return cid

    def set_jurisdiction(self, commitment_id: int, jurisdiction: Jurisdiction) -> None:
        """reviewer fixes who owns the asset, changes where evidence gets searched"""
        if self._policy.commitment(commitment_id) is None:
            raise ValueError(f"unknown commitment {commitment_id}")
        self._policy.set_commitment_jurisdiction(commitment_id, jurisdiction)

    def reject_candidate(self, candidate_id: int) -> None:
        self._policy.set_candidate_status(candidate_id, ReviewStatus.REJECTED)

    def confirm_candidates(self, candidate_ids: list[int]) -> int:
        """batch confirm with suggested type/title, edits stay per item"""
        for cid in candidate_ids:
            candidate = self._policy.candidate(cid)
            if candidate is None or candidate.excerpt_on_page is not True:
                raise ValueError(f"candidate {cid} has no verified source receipt")
        for cid in candidate_ids:
            self.accept_candidate(cid)
        return len(candidate_ids)

    def reject_candidates(self, candidate_ids: list[int]) -> int:
        for cid in candidate_ids:
            self.reject_candidate(cid)
        return len(candidate_ids)

    def reject_all_pending(self) -> int:
        """skip everything left, gives how many"""
        pending = self.queue()
        for cand in pending:
            self._policy.set_candidate_status(cand.id, ReviewStatus.REJECTED)
        return len(pending)

    def queue(self) -> list[PolicyCandidate]:
        return self._policy.candidates(ReviewStatus.UNREVIEWED)

    def accept_link(self, link_id: int,
                    relationship: RelationshipType | None = None) -> None:
        link = self._evidence.link(link_id)
        if link is None:
            raise ValueError(f"unknown link {link_id}")
        self._evidence.decide_link(
            link_id, ReviewStatus.ACCEPTED,
            relationship or link.suggested_relationship,
        )

    def reject_link(self, link_id: int) -> None:
        self._evidence.decide_link(link_id, ReviewStatus.REJECTED)

    def accept_links(
            self,
            link_ids: list[int],
            relationships: dict[int, RelationshipType] | None = None,
    ) -> int:
        """batch accept, each keeps its suggested relationship unless overridden"""
        rel = relationships or {}
        for lid in link_ids:
            self.accept_link(lid, rel.get(lid))
        return len(link_ids)

    def reject_links(self, link_ids: list[int]) -> int:
        for lid in link_ids:
            self.reject_link(lid)
        return len(link_ids)
