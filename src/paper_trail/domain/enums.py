"""Shared enumerations. Deliberately conservative: nothing is inferred
without evidence, and nothing reaches the tracker without human review."""

from enum import StrEnum


class CandidateType(StrEnum):
    OBJECTIVE = "objective"
    MEASURE = "measure"
    TARGET = "target"
    INDICATOR = "indicator"
    BACKGROUND = "background"
    UNCLEAR = "unclear"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RelationshipType(StrEnum):
    """How an official source relates to a policy commitment."""

    DIRECT_IMPLEMENTATION = "direct_implementation"
    SUPPORTING = "supporting"
    BUDGET = "budget"
    INDIRECT = "related_but_indirect"
    UNRELATED = "probably_unrelated"


class Status(StrEnum):
    """What the evidence source itself supports — never the commitment's
    own state, and never inferred beyond the text."""

    ANNOUNCED = "announced"
    PLANNED = "planned"
    IN_PREPARATION = "in_preparation"
    IN_IMPLEMENTATION = "in_implementation"
    COMPLETED = "completed"
    BUDGET = "budget_evidence"
    BACKGROUND = "background_only"
    UNKNOWN = "unknown"


class BudgetKind(StrEnum):
    """Three distinct money concepts. Never merged, never estimated."""

    ESTIMATED_COST = "estimated_cost"
    APPROVED_ALLOCATION = "approved_allocation"
    REPORTED_EXPENDITURE = "reported_expenditure"
