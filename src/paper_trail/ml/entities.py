"""deterministic bits gliner and the llm don't do: money, bare years, status cues

regexes on purpose, money has to be exact and checkable
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ..domain.enums import BudgetKind, Status
from .lang import LanguageProfile

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@lru_cache(maxsize=8)
def _money_re(profile: LanguageProfile) -> re.Pattern:
    # longest first, or "m" eats the start of "million"
    def alt(words):
        return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) or r"(?!)"
    cur, mult = alt(profile.currency_words), alt(profile.multiplier_words)
    # "2,5 millió Ft" or "£2.5 million"
    return re.compile(
        rf"(?P<pre>{cur})\s*(?P<a1>\d[\d\s.,]*\d|\d)\s*(?:(?P<m1>{mult})\b)?"
        rf"|(?P<a2>\d[\d\s.,]*)\s*(?P<m2>{mult})?\s*(?P<post>{cur})(?!\w)", re.IGNORECASE)


def _amount(profile: LanguageProfile, number: str, multiplier: str | None) -> Decimal | None:
    """'300.000 Ft' = 300 000 with decimal commas, '2,5 milliárd' = 2.5 billion.
    decimal, float turns 4,1 milliárd into 4 099 999 999
    """
    raw = re.sub(r"\s+", "", number)
    raw = (raw.replace(".", "").replace(",", ".") if profile.decimal_comma
           else raw.replace(",", ""))
    try:
        return Decimal(raw) * profile.multiplier_words.get((multiplier or "").lower(), 1)
    except InvalidOperation:
        return None


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start)) + 1
    right = text.find(". ", end)
    right = len(text) if right == -1 else right + 1
    return " ".join(text[left:right].split())


def _currency(profile: LanguageProfile, word: str) -> str:
    low = word.lower()
    return next((code for w, code in profile.currency_words.items() if w.lower() == low),
                profile.currency)


@dataclass
class BudgetMention:
    amount_huf: int | None
    amount_raw: str
    kind: BudgetKind | None  # None = money stated, kind unclear
    sentence: str
    year: int | None
    currency: str = ""
    amount_native: str | None = None


def extract_money(text: str, profile: LanguageProfile) -> list[BudgetMention]:
    mentions = []
    for m in _money_re(profile).finditer(text):
        sentence = _sentence_around(text, m.start(), m.end())
        low = sentence.lower()
        kind = next((k for k, cues in profile.budget_cues.items()
                     if any(c in low for c in cues)), None)
        year = _YEAR_RE.search(sentence)
        currency = _currency(profile, m["pre"] or m["post"])
        amount = _amount(profile, m["a1"] or m["a2"], m["m1"] or m["m2"])
        mentions.append(BudgetMention(
            amount_huf=int(amount) if amount is not None and currency == "HUF" else None,
            currency=currency,
            amount_native=None if amount is None else format(amount, "f"),
            amount_raw=" ".join(m.group(0).split()),
            kind=kind, sentence=sentence,
            year=int(year.group()) if year else None))
    return mentions


def years(text: str) -> list[str]:
    """bare years, matching compares these. gliner hands back whole dates"""
    return list(dict.fromkeys(m.group(0) for m in _YEAR_RE.finditer(text)))


def norm_place(raw: str, profile: LanguageProfile) -> str:
    """rough base form for matching: 'Bérkocsis utcában' and 'utcája' both -> 'bérkocsis utcá'"""
    *head, last = raw.lower().split()
    for suffix in profile.place_drop_suffixes:
        if last.endswith(suffix) and len(last) - len(suffix) >= 3:
            last = last[: -len(suffix)]
            break
    return " ".join([*head, last])


# what the source backs up: keyword rules on the matched chunk, never the whole doc

def is_report_doc(url: str, title: str, profile: LanguageProfile) -> bool:
    """big planning docs vs concrete pages, by file type and report words"""
    blob = f"{url} {title}".lower()
    return any(c in blob for c in profile.report_cues)


def classify_status(text: str, profile: LanguageProfile, *,
                    is_report: bool = False,
                    has_money: bool = False) -> tuple[Status, str | None]:
    """what this excerpt itself backs up

    first lifecycle cue wins, strongest first. no cue: money-only = budget evidence,
    a broad report = background, anything else = honestly unclear. conservative on purpose
    """
    lower = text.lower()
    for status, cues in profile.status_rules:
        for cue in cues:
            idx = lower.find(cue)
            if idx != -1:
                return status, _sentence_around(text, idx, idx + len(cue))
    if has_money:
        return Status.BUDGET, None
    if is_report:
        return Status.BACKGROUND, None
    return Status.UNKNOWN, None
