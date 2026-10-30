"""deterministic parsing: orgs, places, dates, money from per-language patterns (lang.py)

no model on purpose, regexes are easy to check
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ..domain.enums import BudgetKind, Status
from .lang import LanguageProfile

# money

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@lru_cache(maxsize=8)
def _compiled(profile: LanguageProfile):
    """every regex a profile needs, compiled once"""
    # longest first, or "m" eats the start of "million"
    cur = "|".join(re.escape(c) for c in sorted(profile.currency_words, key=len, reverse=True))
    cur = cur or r"(?!)"
    mult = ("|".join(re.escape(m) for m in sorted(profile.multiplier_words, key=len,
                                                   reverse=True)) or r"(?!)")
    # "2,5 millió Ft" or "£2.5 million"
    money = re.compile(
        rf"(?P<pre>{cur})\s*(?P<a1>\d[\d\s.,]*\d|\d)\s*(?:(?P<m1>{mult})\b)?"
        rf"|(?P<a2>\d[\d\s.,]*)\s*(?P<m2>{mult})?\s*(?P<post>{cur})(?!\w)", re.IGNORECASE)

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
    """'300.000 Ft' = 300 000 with decimal commas, '2,5 milliárd' = 2.5 billion"""
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
        amount, mult_word = m["a1"] or m["a2"], m["m1"] or m["m2"]
        currency = _currency(profile, m["pre"] or m["post"])
        number = re.sub(r"\s+", "", amount)
        number = (number.replace(".", "").replace(",", ".") if profile.decimal_comma
                  else number.replace(",", ""))
        try:
            native = format(Decimal(number) * Decimal(str(profile.multiplier_words.get(
                (mult_word or "").lower(), 1))), "f")
        except InvalidOperation:
            native = None
        mentions.append(
            BudgetMention(
                amount_huf=(_to_number(profile, amount, mult_word)
                            if currency == "HUF" else None),
                currency=currency, amount_native=native,
                amount_raw=" ".join(m.group(0).split()),
                kind=kind,
                sentence=sentence,
                year=int(y.group()) if y else None,
            )
        )
    return mentions


# dates

def extract_dates(text: str, profile: LanguageProfile) -> list[str]:
    """dates as written: '2024. március 15.', '2030-ra', '2024-ben'"""
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


# orgs and locations

def _norm_place(raw: str, profile: LanguageProfile) -> str:
    """rough base form for matching: 'Losonci téren' -> 'losonci tér'"""
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


# what the source backs up: keyword rules on the matched chunk, never the whole doc

def is_report_doc(url: str, title: str,
                  profile: LanguageProfile) -> bool:
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
