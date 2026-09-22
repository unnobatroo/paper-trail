"""Human review: the only path from pipeline output to the paper trail."""

from __future__ import annotations

from ..domain.enums import CandidateType, RelationshipType, ReviewStatus
from ..domain.models import Commitment, PolicyCandidate
from ..repositories.store import EvidenceRepository, PolicyRepository


class ReviewService:
    def __init__(self, policy: PolicyRepository, evidence: EvidenceRepository):
        self._policy = policy
        self._evidence = evidence

    # commitments -----------------------------------------------------------

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
        )
        cid = self._policy.add_commitment(commitment)
        self._policy.set_candidate_status(candidate_id, ReviewStatus.ACCEPTED)
        return cid

    def reject_candidate(self, candidate_id: int) -> None:
        self._policy.set_candidate_status(candidate_id, ReviewStatus.REJECTED)

    def confirm_candidates(self, candidate_ids: list[int]) -> int:
        """Batch-confirm candidates with their suggested type/title —
        editing stays a per-item action."""
        for cid in candidate_ids:
            self.accept_candidate(cid)
        return len(candidate_ids)

    def reject_candidates(self, candidate_ids: list[int]) -> int:
        for cid in candidate_ids:
            self.reject_candidate(cid)
        return len(candidate_ids)

    def reject_all_pending(self) -> int:
        """Skip every remaining candidate — returns how many were skipped."""
        pending = self.queue()
        for cand in pending:
            self._policy.set_candidate_status(cand.id, ReviewStatus.REJECTED)
        return len(pending)

    def queue(self) -> list[PolicyCandidate]:
        return self._policy.candidates(ReviewStatus.UNREVIEWED)

    # evidence links ----------------------------------------------------------

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
        """Batch-accept links; each keeps its suggested relationship
        unless the reviewer picked another in `relationships`."""
        rel = relationships or {}
        for lid in link_ids:
            self.accept_link(lid, rel.get(lid))
        return len(link_ids)

    def reject_links(self, link_ids: list[int]) -> int:
        for lid in link_ids:
            self.reject_link(lid)
        return len(link_ids)
