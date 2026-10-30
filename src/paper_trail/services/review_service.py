"""human review, the only road from pipeline output to the trail"""

from __future__ import annotations

from ..domain.enums import CandidateType, Jurisdiction, RelationshipType, ReviewStatus
from ..domain.models import Commitment, PolicyCandidate
from ..ml.accountability import PassageAuditor
from ..ml.lang import LanguageProfile
from ..repositories.store import EvidenceRepository, PolicyRepository

# what a commitment inherits from its candidate as is
_CARRIED = {"code", "responsible_org", "timeframe", "deadline_year", "unit", "target_value",
            "source_page"}


class ReviewService:
    def __init__(self, policy: PolicyRepository, evidence: EvidenceRepository,
                 profile: LanguageProfile | None = None):
        self._policy = policy
        self._evidence = evidence
        self._auditor = PassageAuditor(profile or LanguageProfile.empty())

    def _receipted(self, candidate_id: int) -> PolicyCandidate:
        cand = self._policy.candidate(candidate_id)
        if cand is None:
            raise ValueError(f"unknown candidate {candidate_id}")
        if cand.excerpt_on_page is not True or not cand.source_excerpt.strip():
            raise ValueError(f"candidate {candidate_id} has no verified source receipt")
        return cand

    def accept_candidate(self, candidate_id: int, kind: CandidateType | None = None,
                         title: str | None = None, parent_id: int | None = None) -> int:
        cand = self._receipted(candidate_id)
        title = title or cand.normalized_title
        cid = self._policy.add_commitment(Commitment(
            **cand.model_dump(include=_CARRIED), candidate_id=cand.id, parent_id=parent_id,
            kind=kind or cand.suggested_type, title=title, summary=cand.text,
            # owner guessed from the wording, the reviewer can change it
            asset_owner_jurisdiction=self._auditor.jurisdiction(f"{title} {cand.text}")))
        self._policy.set_candidate_status(candidate_id, ReviewStatus.ACCEPTED)
        return cid

    def reject_candidate(self, candidate_id: int) -> None:
        self._policy.set_candidate_status(candidate_id, ReviewStatus.REJECTED)

    def confirm_candidates(self, candidate_ids: list[int]) -> int:
        """batch confirm with the suggested type/title, all receipts checked before any write"""
        for cid in candidate_ids:
            self._receipted(cid)
        return sum(1 for cid in candidate_ids if self.accept_candidate(cid))

    def reject_candidates(self, candidate_ids: list[int]) -> int:
        for cid in candidate_ids:
            self.reject_candidate(cid)
        return len(candidate_ids)

    def reject_all_pending(self) -> int:
        return self.reject_candidates([c.id for c in self.queue()])

    def queue(self) -> list[PolicyCandidate]:
        return self._policy.candidates(ReviewStatus.UNREVIEWED)

    def set_jurisdiction(self, commitment_id: int, jurisdiction: Jurisdiction) -> None:
        """reviewer fixes who owns the asset, that changes where evidence gets searched"""
        if self._policy.commitment(commitment_id) is None:
            raise ValueError(f"unknown commitment {commitment_id}")
        self._policy.set_commitment_jurisdiction(commitment_id, jurisdiction)

    def accept_link(self, link_id: int, relationship: RelationshipType | None = None) -> None:
        link = self._evidence.link(link_id)
        if link is None:
            raise ValueError(f"unknown link {link_id}")
        self._evidence.decide_link(link_id, ReviewStatus.ACCEPTED,
                                   relationship or link.suggested_relationship)

    def reject_link(self, link_id: int) -> None:
        self._evidence.decide_link(link_id, ReviewStatus.REJECTED)

    def accept_links(self, link_ids: list[int],
                     relationships: dict[int, RelationshipType] | None = None) -> int:
        """batch accept, each keeps its suggested relationship unless overridden"""
        for lid in link_ids:
            self.accept_link(lid, (relationships or {}).get(lid))
        return len(link_ids)

    def reject_links(self, link_ids: list[int]) -> int:
        for lid in link_ids:
            self.reject_link(lid)
        return len(link_ids)
