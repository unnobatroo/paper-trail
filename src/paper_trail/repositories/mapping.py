"""db rows -> domain models. pydantic does the coercion, we only decode the json text columns"""

from __future__ import annotations

import json
from collections.abc import Mapping

from ..domain.enums import ArtifactStatus, EvidencePolarity
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

# status only ever escalates: active -> amended -> terminated
ARTIFACT_RANK = {ArtifactStatus.ACTIVE: 0, ArtifactStatus.AMENDED: 1,
                 ArtifactStatus.TERMINATED: 2}
POLARITY_STATUS = {EvidencePolarity.AFFIRMATIVE: ArtifactStatus.ACTIVE,
                   EvidencePolarity.AMENDMENT: ArtifactStatus.AMENDED,
                   EvidencePolarity.TERMINATION: ArtifactStatus.TERMINATED}

# lists stored as json text (schema from the sqlite days)
_JSON = {"organisations", "locations", "dates_mentioned", "flags", "procurement_ids", "parcels",
         "reasons", "shared_organisations", "shared_locations", "shared_dates"}


def _row(row: Mapping) -> dict:
    return {k: json.loads(v) if k in _JSON and isinstance(v, str) else v for k, v in row.items()}


def to_candidate(row: Mapping) -> PolicyCandidate:
    return PolicyCandidate.model_validate(_row(row))


def to_commitment(row: Mapping) -> Commitment:
    return Commitment.model_validate(_row(row))


def to_evidence(row: Mapping) -> EvidenceItem:
    return EvidenceItem.model_validate(_row(row))


def to_budget(row: Mapping) -> BudgetRecord:
    return BudgetRecord.model_validate(_row(row))


def to_official_source(row: Mapping) -> OfficialSource:
    return OfficialSource.model_validate(_row(row))


def to_artifact(row: Mapping) -> ImplementationArtifact:
    return ImplementationArtifact.model_validate(_row(row))


def to_link(row: Mapping) -> EvidenceLink:
    r = _row(row)
    # match features live in flat columns, the model nests them
    r["features"] = MatchFeatures(semantic_similarity=r["similarity"],
                                  **{k: r[k] for k in ("shared_organisations",
                                                       "shared_locations", "shared_dates")})
    return EvidenceLink.model_validate(r)
