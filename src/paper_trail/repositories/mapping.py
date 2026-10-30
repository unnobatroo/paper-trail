"""db rows -> domain models, in one place"""

from __future__ import annotations

import json
from collections.abc import Mapping

from ..domain.enums import (
    ArtifactStatus,
    BudgetKind,
    CandidateType,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
    Status,
)
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    ImplementationArtifact,
    MatchFeatures,
    OfficialSource,
    PolicyCandidate,
)


def column(row: Mapping, name: str, default):
    """columns from migration 010 may be missing on old files"""
    return row[name] if name in row.keys() else default


# status only ever escalates: active -> amended -> terminated
ARTIFACT_RANK = {ArtifactStatus.ACTIVE: 0, ArtifactStatus.AMENDED: 1,
                  ArtifactStatus.TERMINATED: 2}
POLARITY_STATUS = {EvidencePolarity.AFFIRMATIVE: ArtifactStatus.ACTIVE,
                    EvidencePolarity.AMENDMENT: ArtifactStatus.AMENDED,
                    EvidencePolarity.TERMINATION: ArtifactStatus.TERMINATED}


def to_artifact(row: Mapping) -> ImplementationArtifact:
    return ImplementationArtifact(id=row["id"], procurement_id=row["procurement_id"],
                                  status=ArtifactStatus(row["status"]),
                                  status_evidence_id=row["status_evidence_id"])


def to_date(value: str | None):
    from datetime import date

    return date.fromisoformat(value) if isinstance(value, str) else value


def to_candidate(row: Mapping) -> PolicyCandidate:
    return PolicyCandidate(
        id=row["id"],
        document_id=row["document_id"],
        suggested_type=CandidateType(row["suggested_type"]),
        text=row["text"],
        normalized_title=row["normalized_title"],
        source_page=row["source_page"],
        source_excerpt=row["source_excerpt"],
        code=row["code"],
        excerpt_on_page=(bool(row["excerpt_on_page"])
                         if row["excerpt_on_page"] is not None else None),
        responsible_org=row["responsible_org"],
        timeframe=row["timeframe"],
        deadline_year=row["deadline_year"],
        unit=row["unit"],
        target_value=row["target_value"],
        review_status=ReviewStatus(row["review_status"]),
    )


def to_commitment(row: Mapping) -> Commitment:
    return Commitment(
        id=row["id"],
        candidate_id=row["candidate_id"],
        parent_id=row["parent_id"],
        kind=CandidateType(row["kind"]),
        title=row["title"],
        summary=row["summary"],
        code=row["code"],
        responsible_org=row["responsible_org"],
        timeframe=row["timeframe"],
        deadline_year=row["deadline_year"],
        unit=row["unit"],
        target_value=row["target_value"],
        source_page=row["source_page"],
        asset_owner_jurisdiction=Jurisdiction(
            column(row, "asset_owner_jurisdiction", Jurisdiction.DISTRICT_MUNICIPALITY.value)),
    )


def to_evidence(row: Mapping) -> EvidenceItem:
    return EvidenceItem(
        id=row["id"],
        commitment_id=row["commitment_id"],
        url=row["url"],
        title=row["title"],
        publisher=row["publisher"],
        published_on=to_date(row["published_on"]),
        snippet=row["snippet"],
        organisations=json.loads(row["organisations"]),
        locations=json.loads(row["locations"]),
        dates_mentioned=json.loads(row["dates_mentioned"]),
        status_hint=Status(row["status_hint"]),
        status_excerpt=row["status_excerpt"],
        polarity=EvidencePolarity(column(row, "polarity", "affirmative")),
        flags=json.loads(column(row, "flags", "[]")),
        procurement_ids=json.loads(column(row, "procurement_ids", "[]")),
        parcels=json.loads(column(row, "parcels", "[]")),
    )


def to_link(row: Mapping) -> EvidenceLink:
    return EvidenceLink(
        id=row["id"],
        commitment_id=row["commitment_id"],
        evidence_id=row["evidence_id"],
        score=row["score"],
        suggested_relationship=RelationshipType(row["suggested_relationship"]),
        reasons=json.loads(row["reasons"]),
        relationship=RelationshipType(row["relationship"]) if row["relationship"] else None,
        review_status=ReviewStatus(row["review_status"]),
        features=MatchFeatures(
            semantic_similarity=row["similarity"],
            shared_organisations=json.loads(row["shared_organisations"]),
            shared_locations=json.loads(row["shared_locations"]),
            shared_dates=json.loads(row["shared_dates"]),
        ),
    )


def to_budget(row: Mapping) -> BudgetRecord:
    return BudgetRecord(
        id=row["id"],
        evidence_id=row["evidence_id"],
        kind=BudgetKind(row["kind"]),
        amount_huf=row["amount_huf"],
        currency=row["currency"] if "currency" in row.keys() else "HUF",
        amount_native=row["amount_native"] if "amount_native" in row.keys() else None,
        amount_raw=row["amount_raw"],
        fiscal_year=row["fiscal_year"],
        description=row["description"],
        source_url=row["source_url"],
    )


def to_official_source(row: Mapping) -> OfficialSource:
    owner = column(row, "jurisdiction", None)
    return OfficialSource(id=row["id"], url=row["url"], title=row["title"],
                          publisher=row["publisher"], sort_order=row["sort_order"],
                          jurisdiction=Jurisdiction(owner) if owner else None)
