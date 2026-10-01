"""Deterministic parsing of municipal text — language-agnostic engine.

Orgs, locations, dates and money are extracted with patterns compiled from
a `LanguageProfile` (see `lang.py`) — a language model is not needed for
this and would be harder to verify. Every returned mention keeps the
verbatim text it came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ..domain.enums import BudgetKind, Status
from .lang import LanguageProfile

# ---------------------------------------------------------------------------
# Money

_AMOUNT = r"(\d[\d\s.,]*)"
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@lru_cache(maxsize=8)
def _compiled(profile: LanguageProfile):
    """All regexes a profile needs, built once per profile."""
    cur = "|".join(re.escape(c) for c in profile.currency_words) or r"(?!)"
    mult = ("|".join(re.escape(m) for m in profile.multiplier_words)
            or r"(?!)")
    money = re.compile(
        _AMOUNT + rf"\s*({mult})?\s*({cur})\b", re.IGNORECASE)

    date = None
    if profile.months_re:
        date = re.compile(
            rf"\b(20\d{{2}})[.\s]+({profile.months_re})[a-z]*\.?\s*"
            r"(\d{1,2})?", re.IGNORECASE)

    org = None
    if profile.org_suffixes_re or profile.org_names_re:
        parts = []
        if profile.org_suffixes_re:
            up, low = profile.upper_chars, profile.lower_chars
            parts.append(
                rf"[{up}][\w{low}.-]*(?:\s+[{up}{low}][\w{low}.-]*){{0,4}}"
                rf"\s(?:{profile.org_suffixes_re})")
        if profile.org_names_re:
            parts.append(profile.org_names_re)
        org = re.compile(r"\b(" + "|".join(parts) + r")")

    place = None
    if profile.place_words_re:
        up = profile.upper_chars
        place = re.compile(
            rf"\b([{up}][\w{profile.lower_chars}.]+"
            rf"(?:\s+[{up}][\w{profile.lower_chars}.]+){{0,2}})"
            rf"\s*({profile.place_words_re})\b")

    intent = (re.compile(profile.intent_re, re.IGNORECASE)
              if profile.intent_re else None)

    value = None
    if profile.units_re:
        value = re.compile(
            rf"(\d[\d\s]*(?:[.,]\d+)?)\s*({profile.units_re})")

    return money, date, org, place, intent, value


def _to_number(profile: LanguageProfile, number: str,
               multiplier_word: str | None) -> int | None:
    """Locale-aware amount normalisation: '300.000 Ft' is 300 000 with a
    decimal-comma profile, '2,5 milliárd' is 2.5 billion."""
    raw = number.replace(" ", "").replace("\u00a0", "")
    if profile.decimal_comma:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    value *= profile.multiplier_words.get((multiplier_word or "").lower(),
                                          1)
    return int(value)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start)) + 1
    right = text.find(". ", end)
    right = len(text) if right == -1 else right + 1
    return " ".join(text[left:right].split())


@dataclass
class BudgetMention:
    amount_huf: int | None
    amount_raw: str
    kind: BudgetKind | None  # None = explicitly stated money, kind unclear
    sentence: str
    year: int | None


def extract_money(text: str,
                  profile: LanguageProfile) -> list[BudgetMention]:
    money_re, _, _, _, _, _ = _compiled(profile)
    mentions: list[BudgetMention] = []
    for m in money_re.finditer(text):
        sentence = _sentence_around(text, m.start(), m.end())
        kind = next(
            (k for k, cues in profile.budget_cues.items()
             if any(c in sentence.lower() for c in cues)),
            None,
        )
        y = _YEAR_RE.search(sentence)
        mentions.append(
            BudgetMention(
                amount_huf=_to_number(profile, m.group(1), m.group(2)),
                amount_raw=" ".join(m.group(0).split()),
                kind=kind,
                sentence=sentence,
                year=int(y.group()) if y else None,
            )
        )
    return mentions


# ---------------------------------------------------------------------------
# Dates

def extract_dates(text: str, profile: LanguageProfile) -> list[str]:
    """Verbatim date mentions: full dates like '2024. március 15.' and
    bare years like '2030-ra' / '2024-ben'."""
    _, date_re, _, _, _, _ = _compiled(profile)
    found = []
    if date_re is not None:
        found += [" ".join(m.group(0).split()) for m in date_re.finditer(text)]
    found += [m.group(0) for m in _YEAR_RE.finditer(text)]
    seen, out = set(), []
    for d in found:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Organisations and locations

def _norm_place(raw: str, profile: LanguageProfile) -> str:
    """Rough base form for matching: 'Losonci téren' → 'losonci tér'."""
    words = raw.lower().split()
    last = words[-1]
    for suffix in profile.place_drop_suffixes:
        if last.endswith(suffix) and len(last) - len(suffix) >= 3:
            last = last[: -len(suffix)]
            break
    words[-1] = last
    return " ".join(words)


def extract_organisations(text: str,
                          profile: LanguageProfile) -> list[str]:
    _, _, org_re, _, _, _ = _compiled(profile)
    if org_re is None:
        return []
    seen, out = set(), []
    for m in org_re.finditer(text):
        name = " ".join(m.group(0).split())
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def extract_locations(text: str,
                      profile: LanguageProfile) -> list[str]:
    _, _, _, place_re, _, _ = _compiled(profile)
    if place_re is None:
        return []
    seen, out = set(), []
    for m in place_re.finditer(text):
        raw = " ".join(m.group(0).split())
        key = _norm_place(raw, profile)
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


# ---------------------------------------------------------------------------
# What the source itself supports — keyword rules over the matched excerpt,
# never inferred. Evaluated on the retrieved chunk, not the whole document:
# a 100-page report always contains every cue somewhere.

def is_report_doc(url: str, title: str,
                  profile: LanguageProfile) -> bool:
    """Broad planning documents vs concrete pages — cues like file
    extensions and report-type words from the profile."""
    blob = f"{url} {title}".lower()
    return any(c in blob for c in profile.report_cues)


def classify_status(text: str, profile: LanguageProfile, *,
                    is_report: bool = False,
                    has_money: bool = False) -> tuple[Status, str | None]:
    """What this excerpt itself supports.

    First lifecycle cue wins, strongest claim first. With no lifecycle cue:
    money-only text is budget evidence; a broad report without cues is
    background material; anything else is honestly unclear. Conservative by
    design — a missed status is better than a claimed one.
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
