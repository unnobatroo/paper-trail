"""Simple, inspectable matching between a commitment and an evidence passage.

A weighted score — nothing learned, nothing hidden:

    score = 0.60 * semantic_similarity
          + 0.15 * (shared organisations, capped at 2)
          + 0.15 * (shared locations, capped at 2)
          + 0.10 * (shared dates/years, capped at 2)

The relationship suggestion is a transparent rule set over those components.
A human still decides.
"""

from __future__ import annotations

from ..domain.enums import RelationshipType
from ..domain.models import Commitment, EvidenceItem, MatchFeatures
from .entities import (
    _norm_place,
    extract_locations,
    extract_organisations,
)

W_SIMILARITY = 0.60
W_ORG = 0.15
W_LOCATION = 0.15
W_DATE = 0.10

DIRECT_SIMILARITY = 0.72
SUPPORTING_SIMILARITY = 0.60
INDIRECT_SIMILARITY = 0.45


def _norm(names: list[str]) -> set[str]:
    return {n.lower().strip() for n in names}


def _shared(a: set[str], b: set[str]) -> set[str]:
    """Exact or containing match — 'RÉV8' should match 'RÉV8 Zrt.'."""
    out = set()
    for x in a:
        for y in b:
            if x == y or (len(x) > 4 and len(y) > 4 and (x in y or y in x)):
                out.add(y if len(y) < len(x) else x)
    return out


def commitment_entities(commitment: Commitment) -> dict[str, set[str]]:
    """Entities visible in the commitment text itself."""
    text = " ".join([commitment.title, commitment.summary])
    orgs = _norm(extract_organisations(text))
    if commitment.responsible_org:
        orgs |= _norm([commitment.responsible_org])
    locs = {_norm_place(l) for l in extract_locations(text)}
    dates = {str(commitment.deadline_year)} if commitment.deadline_year else set()
    return {"orgs": orgs, "locations": locs, "dates": dates}


def compute_features(commitment: Commitment, evidence: EvidenceItem,
                     similarity: float) -> MatchFeatures:
    ce = commitment_entities(commitment)
    return MatchFeatures(
        semantic_similarity=round(similarity, 4),
        shared_organisations=sorted(_shared(ce["orgs"], _norm(evidence.organisations))),
        shared_locations=sorted(
            _shared(ce["locations"], {_norm_place(l) for l in evidence.locations})
        ),
        shared_dates=sorted(ce["dates"] & set(evidence.dates_mentioned)),
    )


def score(features: MatchFeatures) -> float:
    return min(1.0, round(
        W_SIMILARITY * features.semantic_similarity
        + W_ORG * min(len(features.shared_organisations), 2) / 2
        + W_LOCATION * min(len(features.shared_locations), 2) / 2
        + W_DATE * min(len(features.shared_dates), 2) / 2,
        4,
    ))


def suggest_relationship(features: MatchFeatures,
                         has_budget: bool) -> tuple[RelationshipType, list[str]]:
    reasons: list[str] = []
    sim = features.semantic_similarity

    if sim >= DIRECT_SIMILARITY:
        reasons.append("the text is a close match")
    elif sim >= SUPPORTING_SIMILARITY:
        reasons.append("the text is fairly similar")
    elif sim >= INDIRECT_SIMILARITY:
        reasons.append("some text overlap")
    else:
        reasons.append("little text in common")

    if features.shared_organisations:
        reasons.append("names the same organisation: "
                       + ", ".join(features.shared_organisations))
    if features.shared_locations:
        reasons.append("same place: " + ", ".join(features.shared_locations))
    if features.shared_dates:
        reasons.append("same year: " + ", ".join(features.shared_dates))
    if has_budget:
        reasons.append("the page mentions a money figure")

    if sim >= DIRECT_SIMILARITY and (features.shared_organisations or features.shared_locations):
        return RelationshipType.DIRECT_IMPLEMENTATION, reasons
    if has_budget and sim >= INDIRECT_SIMILARITY:
        return RelationshipType.BUDGET, reasons
    if sim >= SUPPORTING_SIMILARITY:
        return RelationshipType.SUPPORTING, reasons
    if sim >= INDIRECT_SIMILARITY:
        return RelationshipType.INDIRECT, reasons
    return RelationshipType.UNRELATED, reasons
