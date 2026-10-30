"""shared enums. nothing inferred without evidence, nothing counts without review"""

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
    """what the source says, never what we guess about the commitment"""

    ANNOUNCED = "announced"
    PLANNED = "planned"
    IN_PREPARATION = "in_preparation"
    IN_IMPLEMENTATION = "in_implementation"
    COMPLETED = "completed"
    BUDGET = "budget_evidence"
    BACKGROUND = "background_only"
    UNKNOWN = "unknown"


class BudgetKind(StrEnum):
    """money along the budget cycle, never merged or summed across kinds

    estimate -> decree -> amended decree -> contract -> final accounts (zárszámadás).
    REPORTED_EXPENDITURE = a report says it was spent, which isn't the audited final account
    """

    ESTIMATED_COST = "estimated_cost"
    INITIAL_APPROPRIATION = "initial_appropriation"
    AMENDED_APPROPRIATION = "amended_appropriation"
    CONTRACTED_PRICE = "contracted_price"
    ACTUAL_EXPENDITURE = "actual_expenditure"
    REPORTED_EXPENDITURE = "reported_expenditure"

    @classmethod
    def _missing_(cls, value):
        # old rows from before migration 010
        return cls.INITIAL_APPROPRIATION if value == "approved_allocation" else None


class EvidencePolarity(StrEnum):
    """what a passage does to the work. a cancellation is evidence too"""

    AFFIRMATIVE = "affirmative"
    AMENDMENT = "amendment"
    TERMINATION = "termination"


class EvidenceFlag(StrEnum):
    """warnings for the reviewer, they never decide anything"""

    # someone later amended/cancelled the contract this passage is about
    REGRESSION_WARNING = "regression_warning"
    # repair talk, zero upgrade talk. probably not climate action
    MAINTENANCE_ONLY_SUSPECT = "maintenance_only_suspect"


class Jurisdiction(StrEnum):
    """who owns the asset, i.e. whose sites the evidence lives on"""

    DISTRICT_MUNICIPALITY = "district_municipality"
    METROPOLITAN_MUNICIPALITY = "metropolitan_municipality"
    PUBLIC_UTILITY_WATER = "public_utility_water"
    PUBLIC_UTILITY_HEATING = "public_utility_heating"
    NATIONAL_GOVERNMENT = "national_government"


class ArtifactStatus(StrEnum):
    """contract/project lifecycle, only ever escalates"""

    ACTIVE = "active"
    AMENDED = "amended"
    TERMINATED = "terminated"
