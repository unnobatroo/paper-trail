"""Transparent matching: visible features, bounded score, sensible suggestions."""

from paper_trail.domain.enums import CandidateType, RelationshipType
from paper_trail.domain.models import Commitment, EvidenceItem
from paper_trail.ml.matching import compute_features, score, suggest_relationship

COM = Commitment(
    kind=CandidateType.MEASURE,
    title="Utcai fasorok telepítése",
    summary="Fák ültetése a Bérkocsis utcában a RÉV8 bevonásával.",
    responsible_org="RÉV8 Zrt.",
    deadline_year=2030,
)


def _ev(**kw) -> EvidenceItem:
    base = dict(commitment_id=1, url="https://rev8.hu/x", title="x")
    base.update(kw)
    return EvidenceItem(**base)


def test_features_pick_up_shared_entities():
    ev = _ev(organisations=["RÉV8 Zrt."], locations=["Bérkocsis utcában"],
             dates_mentioned=["2030"])
    f = compute_features(COM, ev, similarity=0.8)
    assert f.shared_organisations
    assert f.shared_locations
    assert f.shared_dates == ["2030"]
    assert 0 < score(f) <= 1.0


def test_strong_match_with_shared_org_is_direct():
    ev = _ev(organisations=["RÉV8"], locations=[])
    f = compute_features(COM, ev, similarity=0.85)
    rel, reasons = suggest_relationship(f, has_budget=False)
    assert rel == RelationshipType.DIRECT_IMPLEMENTATION
    assert reasons


def test_low_similarity_is_unrelated():
    f = compute_features(COM, _ev(), similarity=0.1)
    rel, _ = suggest_relationship(f, has_budget=False)
    assert rel == RelationshipType.UNRELATED
