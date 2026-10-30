"""audit rules, read one matched passage, never the whole doc

they only add hints and warnings. accepting stuff is ReviewService's job, full stop
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from ..domain.enums import (
    ArtifactStatus,
    BudgetKind,
    EvidenceFlag,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
)
from ..domain.models import BudgetRecord, EvidenceItem, ImplementationArtifact
from .lang import LanguageProfile

# EKR001234562021 = public procurement, VEKOP-6.2.1-15-2016-00001 = eu programme
_PROCUREMENT_RE = re.compile(
    r"\bEKR\d{9,12}\b|"
    r"\b(?:VEKOP|KEHOP|GINOP|EFOP|TOP|TOP_PLUSZ|KEHOP_PLUSZ|VP)(?:-[\dA-Z.]+){3,6}\b")
# "36542/1 hrsz.", "hrsz.: 36542/1", "36542/1 helyrajzi számú"
_PARCEL_RE = re.compile(
    r"(?:\bhrsz\.?\s*:?\s*(\d{3,6}(?:/\d{1,4}){0,2}))|"
    r"(?:\b(\d{3,6}(?:/\d{1,4}){0,2})\s*(?:hrsz\b|helyrajzi\s+sz))", re.I)

# flagged passages never get an auto hint above INDIRECT
_CAPPED = {RelationshipType.DIRECT_IMPLEMENTATION, RelationshipType.SUPPORTING,
           RelationshipType.BUDGET}
_FLAG_REASONS = {
    EvidenceFlag.REGRESSION_WARNING:
        "the contract or project was later amended or cancelled, automatic hint blocked",
    EvidenceFlag.MAINTENANCE_ONLY_SUSPECT:
        "repair or maintenance wording without upgrade wording, may not be climate action",
}


def _has(text: str, cues: Iterable[str]) -> bool:
    low = text.lower()
    return any(c in low for c in cues)


@dataclass(frozen=True)
class PassageAudit:
    """what one passage says about the work it describes"""

    polarity: EvidencePolarity = EvidencePolarity.AFFIRMATIVE
    flags: list[EvidenceFlag] = field(default_factory=list)
    procurement_ids: list[str] = field(default_factory=list)
    parcels: list[str] = field(default_factory=list)


class PassageAuditor:
    """per-passage cue rules: polarity, maintenance, ids, parcels, owner"""

    def __init__(self, profile: LanguageProfile):
        self._profile = profile

    def audit(self, text: str) -> PassageAudit:
        return PassageAudit(polarity=self.polarity(text), flags=self.flags(text),
                            procurement_ids=self.procurement_ids(text),
                            parcels=self.parcels(text))

    def polarity(self, text: str) -> EvidencePolarity:
        """termination beats amendment, amended-then-cancelled is cancelled"""
        if _has(text, self._profile.termination_cues):
            return EvidencePolarity.TERMINATION
        if _has(text, self._profile.amendment_cues):
            return EvidencePolarity.AMENDMENT
        return EvidencePolarity.AFFIRMATIVE

    def flags(self, text: str) -> list[EvidenceFlag]:
        """fixing potholes isn't climate action unless something got upgraded"""
        if (_has(text, self._profile.maintenance_cues)
                and not _has(text, self._profile.upgrade_cues)):
            return [EvidenceFlag.MAINTENANCE_ONLY_SUSPECT]
        return []

    def jurisdiction(self, text: str) -> Jurisdiction:
        """first owner whose cue shows up: utilities, then the city, then the state"""
        for jurisdiction, cues in self._profile.jurisdiction_cues.items():
            if _has(text, cues):
                return jurisdiction
        return Jurisdiction.DISTRICT_MUNICIPALITY

    @staticmethod
    def procurement_ids(text: str) -> list[str]:
        return list(dict.fromkeys(m.group(0) for m in _PROCUREMENT_RE.finditer(text)))

    @staticmethod
    def parcels(text: str) -> list[str]:
        return list(dict.fromkeys(m.group(1) or m.group(2) for m in _PARCEL_RE.finditer(text)))

    @staticmethod
    def effective_flags(evidence: EvidenceItem,
                        artifacts: Iterable[ImplementationArtifact]) -> list[EvidenceFlag]:
        """stored flags + a regression warning if another passage killed or changed a contract
        this one names. computed on read so it hits evidence that's already accepted
        """
        flags = list(evidence.flags)
        regressed = any(a.status != ArtifactStatus.ACTIVE
                        and a.status_evidence_id != evidence.id for a in artifacts)
        if regressed and EvidenceFlag.REGRESSION_WARNING not in flags:
            flags.append(EvidenceFlag.REGRESSION_WARNING)
        return flags

    @staticmethod
    def cap(rel: RelationshipType, reasons: list[str], flags: Iterable[EvidenceFlag]
            ) -> tuple[RelationshipType, list[str]]:
        """a person can still accept a flagged passage, the machine just won't vouch for it"""
        flags = [f for f in flags if f in _FLAG_REASONS]
        if not flags:
            return rel, reasons
        reasons = reasons + [_FLAG_REASONS[f] for f in flags]
        return (RelationshipType.INDIRECT if rel in _CAPPED else rel), reasons


# appropriations we hold against the final accounts, newest first
_APPROPRIATIONS = (BudgetKind.AMENDED_APPROPRIATION, BudgetKind.INITIAL_APPROPRIATION)


@dataclass
class FinancialSummary:
    """what accepted money evidence proves, per kind, never summed"""

    states: list[BudgetKind]
    executed: bool  # final accounts figure or a signed handover cert
    findings: list[str]


class FinancialAuditor:
    """budget state rules: only final accounts or a handover cert prove money got spent"""

    def __init__(self, profile: LanguageProfile):
        self._profile = profile

    def summarize(self, budgets: list[BudgetRecord],
                  evidence: list[EvidenceItem]) -> FinancialSummary:
        states = [k for k in BudgetKind if any(b.kind == k for b in budgets)]
        certificate = any(_has(e.snippet, self._profile.completion_certificate_cues)
                          for e in evidence)
        executed = BudgetKind.ACTUAL_EXPENDITURE in states or certificate
        findings = []
        if (BudgetKind.REPORTED_EXPENDITURE in states
                and BudgetKind.ACTUAL_EXPENDITURE not in states):
            findings.append("Spending is only reported, not confirmed by the final accounts "
                            "(zárszámadás).")
        if any(k in states for k in _APPROPRIATIONS) and not executed:
            findings.append("Money was appropriated but no final accounts figure or "
                            "completion certificate confirms it was spent.")
        findings += self._unspent(budgets)
        return FinancialSummary(states=states, executed=executed, findings=findings)

    @staticmethod
    def _unspent(budgets: list[BudgetRecord]) -> list[str]:
        """latest appropriation vs final accounts, same year + currency only"""
        by_key: dict[tuple, dict[BudgetKind, Decimal]] = {}
        for b in budgets:
            # decimal, float rounds big forint sums and drops euro cents
            value = (Decimal(b.amount_native) if b.amount_native
                     else None if b.amount_huf is None else Decimal(b.amount_huf))
            if value is None or b.fiscal_year is None:
                continue
            slot = by_key.setdefault((b.fiscal_year, b.currency), {})
            slot[b.kind] = max(slot.get(b.kind, 0), value)
        out = []
        for (year, currency), kinds in sorted(by_key.items()):
            planned = next((kinds[k] for k in _APPROPRIATIONS if k in kinds), None)
            spent = kinds.get(BudgetKind.ACTUAL_EXPENDITURE)
            if planned and spent is not None and spent < planned:
                out.append(f"{year}: {planned - spent:,} {currency} of the appropriation was "
                           f"not spent ({spent:,} of {planned:,}).".replace(",", " "))
        return out
