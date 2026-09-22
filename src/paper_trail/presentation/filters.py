"""Pure list-filter helpers for the review screens — no Streamlit here so
the filtering rules stay unit-testable."""

from __future__ import annotations

from ..domain.enums import CandidateType, ReviewStatus
from ..domain.models import PolicyCandidate

STATUS_ALL = "All"
STATUS_PENDING = "Needs review"
STATUS_CONFIRMED = "Confirmed"
STATUS_REJECTED = "Rejected"

_STATUS_MAP = {
    STATUS_PENDING: ReviewStatus.UNREVIEWED,
    STATUS_CONFIRMED: ReviewStatus.ACCEPTED,
    STATUS_REJECTED: ReviewStatus.REJECTED,
}

_TYPE_MAP = {
    "Objectives": CandidateType.OBJECTIVE,
    "Measures": CandidateType.MEASURE,
    "Targets": CandidateType.TARGET,
}


def filter_candidates(
    candidates: list[PolicyCandidate],
    query: str = "",
    type_label: str = "All",
    status_label: str = STATUS_PENDING,
) -> list[PolicyCandidate]:
    """Search + type + status filter for the commitment review list.

    `type_label` is one of "All" / "Objectives" / "Measures" / "Targets";
    `status_label` is one of the STATUS_* constants. Unchecked/unclear
    candidates (excerpt not re-found) stay visible under every status.
    """
    out = candidates

    want_status = _STATUS_MAP.get(status_label)
    if want_status is not None:
        out = [c for c in out if c.review_status == want_status]

    want_type = _TYPE_MAP.get(type_label)
    if want_type is not None:
        out = [c for c in out if c.suggested_type == want_type]

    q = query.strip().lower()
    if q:
        out = [
            c for c in out
            if q in (c.normalized_title or "").lower()
            or q in (c.text or "").lower()
            or q in (c.code or "").lower()
        ]
    return out
