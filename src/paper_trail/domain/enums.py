"""shared enums, nothing inferred without evidence, nothing tracked without review"""

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
    """how a source relates to a commitment"""

    DIRECT_IMPLEMENTATION = "direct_implementation"
    SUPPORTING = "supporting"
    BUDGET = "budget"
    INDIRECT = "related_but_indirect"
    UNRELATED = "probably_unrelated"


class Status(StrEnum):
    """what the source says, not the commitment's state, nothing beyond the text"""

    ANNOUNCED = "announced"
    PLANNED = "planned"
    IN_PREPARATION = "in_preparation"
    IN_IMPLEMENTATION = "in_implementation"
    COMPLETED = "completed"
    BUDGET = "budget_evidence"
    BACKGROUND = "background_only"
    UNKNOWN = "unknown"


class BudgetKind(StrEnum):
    """three money concepts, never merged or estimated"""

    ESTIMATED_COST = "estimated_cost"
    APPROVED_ALLOCATION = "approved_allocation"
    REPORTED_EXPENDITURE = "reported_expenditure"
