"""Deterministic parsing of Hungarian municipal text.

Orgs, locations, dates and money are extracted with patterns — a language model
is not needed for this and would be harder to verify. Every returned mention
keeps the verbatim text it came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.enums import BudgetKind, Status

# ---------------------------------------------------------------------------
# Money

_AMOUNT = r"(\d[\d\s.,]*)"
_MONEY_RE = re.compile(
    _AMOUNT + r"\s*(milliárd|millió|ezer|Mrd|mrd|M)?\s*(Ft|forint)\b",
    re.IGNORECASE,
)

# Cue words deciding the budget kind. Only explicit wording counts — an
# ambiguous figure stays unclassified rather than being guessed.
_CUES = {
    BudgetKind.ESTIMATED_COST: [
        "becsült", "várható költség", "tervezett költség", "előirányzat",
    ],
    BudgetKind.APPROVED_ALLOCATION: [
        "támogatást nyert", "támogatást kap", "elnyert", "nyert összeg",
        "költségkeret", "keretösszeg", "keretből", "pályázati keret",
        "támogatási szerződés", "forint támogatás", "forintra",
        "igényelhető", "megállapított", "jóváhagyott", "különített el",
        "forintot különít",
    ],
    BudgetKind.REPORTED_EXPENDITURE: [
        "kifizetés", "kifizetésre került", "költöttek", "elköltött",
        "elszámolt", "felmerült költség", "került sor",
    ],
}

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_HU_MONTHS = (
    "január|február|március|április|május|június|július|augusztus|"
    "szeptember|október|november|december"
)
_DATE_RE = re.compile(
    r"\b(20\d{2})[.\s]+(" + _HU_MONTHS + r")[a-z]*\.?\s*(\d{1,2})?",
    re.IGNORECASE,
)


@dataclass
class BudgetMention:
    amount_huf: int | None
    amount_raw: str
    kind: BudgetKind | None  # None = explicitly stated money, kind unclear
    sentence: str
    year: int | None


def _to_huf(number: str, multiplier_word: str | None) -> int | None:
    # Hungarian convention: '.' and ' ' are thousand separators, ',' is the
    # decimal mark — '300.000 Ft' is 300 000, '2,5 milliárd' is 2.5 billion.
    raw = (number.replace(" ", "").replace("\u00a0", "")
           .replace(".", "").replace(",", "."))
    try:
        value = float(raw)
    except ValueError:
        return None
    word = (multiplier_word or "").lower()
    if word in ("milliárd", "mrd"):
        value *= 1_000_000_000
    elif word == "millió":
        value *= 1_000_000
    elif word == "ezer":
        value *= 1_000
    return int(value)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start)) + 1
    right = text.find(". ", end)
    right = len(text) if right == -1 else right + 1
    return " ".join(text[left:right].split())


def extract_money(text: str) -> list[BudgetMention]:
    mentions: list[BudgetMention] = []
    for m in _MONEY_RE.finditer(text):
        sentence = _sentence_around(text, m.start(), m.end())
        kind = next(
            (k for k, cues in _CUES.items() if any(c in sentence.lower() for c in cues)),
            None,
        )
        y = _YEAR_RE.search(sentence)
        mentions.append(
            BudgetMention(
                amount_huf=_to_huf(m.group(1), m.group(2)),
                amount_raw=" ".join(m.group(0).split()),
                kind=kind,
                sentence=sentence,
                year=int(y.group()) if y else None,
            )
        )
    return mentions


# ---------------------------------------------------------------------------
# Dates


def extract_dates(text: str) -> list[str]:
    """Verbatim date mentions: full dates like '2024. március 15.' and
    bare years like '2030-ra' / '2024-ben'."""
    found = [" ".join(m.group(0).split()) for m in _DATE_RE.finditer(text)]
    found += [m.group(0) for m in _YEAR_RE.finditer(text)]
    seen, out = set(), []
    for d in found:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


# ---------------------------------------------------------------------------
# Organisations and locations

_ORG_RE = re.compile(
    r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüű.-]*(?:\s+[A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű.-]*){0,4}"
    r"\s(?:Zrt\.?|Kft\.?|Önkormányzat[a-záéíóöőúüű]*|Iroda|Központ|Egyesület|"
    r"Alapítvány|Hivatal[a-záéíóöőúüű]*)|"
    r"RÉV8|Rév8|JGK|FŐKERT|Főkert|BKV|BKK|Józsefvárosi Önkormányzat|"
    r"Budapest Főváros Önkormányzat[a-záéíóöőúüű]*)"
)

_PLACE_RE = re.compile(
    r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüű.]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüű.]+){0,2})"
    r"\s*(tér|tere|téren|téri|utca|utcában|utcába|utcáján|utcai|út|úton|köz|"
    r"sétány|sétányt|park|parkja|kert|kertje|lakótelep)\b"
)


def _norm_place(raw: str) -> str:
    """Rough base form for matching: 'Losonci téren' → 'losonci tér'."""
    words = raw.lower().split()
    last = words[-1]
    for suffix in ("ban", "ba", "ján", "ja", "én", "re", "n", "t", "i", "e"):
        if last.endswith(suffix) and len(last) - len(suffix) >= 3:
            last = last[: -len(suffix)]
            break
    words[-1] = last
    return " ".join(words)


def extract_organisations(text: str) -> list[str]:
    seen, out = set(), []
    for m in _ORG_RE.finditer(text):
        name = " ".join(m.group(0).split())
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


def extract_locations(text: str) -> list[str]:
    seen, out = set(), []
    for m in _PLACE_RE.finditer(text):
        raw = " ".join(m.group(0).split())
        key = _norm_place(raw)
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


# ---------------------------------------------------------------------------
# What the source itself supports — keyword rules over the matched excerpt,
# never inferred. Evaluated on the retrieved chunk, not the whole document:
# a 100-page report always contains every cue somewhere.

# Broad planning documents vs concrete pages — used both for the "report vs
# project" display label and for the background-only fallback below.
_REPORT_CUES = (
    ".pdf", "beszámoló", "secap", "stratégia", "akcióterv", "tanulmány",
    "intézkedési terv", "koncepcio", "koncepció", "program 20", "program-",
    "melleklet", "tervezet",
)


def is_report_doc(url: str, title: str) -> bool:
    blob = f"{url} {title}".lower()
    return any(c in blob for c in _REPORT_CUES)


_STATUS_RULES: list[tuple[Status, list[str]]] = [
    (Status.COMPLETED, [
        "elkészült", "megvalósult", "átadták", "átadásra került", "megújult",
        "fejeződtek be", "befejeződött", "ültettek el", "elültetésre került",
        "elültették", "ültetésre került", "telepítettünk", "létesült",
        "megnyílt", "jött létre", "létrejött", "megépült", "készült el",
        "megvalósítottuk", "megnyitottuk", "átadtuk", "átadását",
    ]),
    (Status.IN_IMPLEMENTATION, [
        "kivitelezés folyamatban", "kivitelezése folyamatban", "munkálatok",
        "a munkák megkezdődtek", "munka megkezdődött", "felbontjuk",
        "feltörjük", "megújítása zajlik", "felújítás zajlik", "építkezés",
        "kivitelezés zajlik", "kivitelezését",
    ]),
    (Status.IN_PREPARATION, [
        "tervezés folyamatban", "előkészítés", "tervezzük", "véleményezhetik",
        "koncepcióterv", "lakossági fórum", "kiviteli terv", "engedélyeztetés",
        "előkészítése folyamatban", "közösségi tervezés", "tervezik meg",
        "egyeztetésre kerül", "társadalmi egyeztetés",
    ]),
    (Status.ANNOUNCED, [
        "bejelentette", "bejelentés", "kiírjuk", "kiírásra kerül",
        "meghirdette", "meghirdetésre kerül", "pályázatot indít",
        "pályázatot hirdet", "indul a pályázat", "indul a program",
        "pályázni lehet", "nyílt pályázat",
    ]),
    (Status.PLANNED, [
        "tervezett", "tervei szerint", "nyertes ötlet", "javaslat",
        "tervezik", "valósuljon meg", "megvalósításra kerül",
        "megvalósítását tervezi",
    ]),
]


def classify_status(text: str, *, is_report: bool = False,
                    has_money: bool = False) -> tuple[Status, str | None]:
    """What this excerpt itself supports.

    First lifecycle cue wins, strongest claim first. With no lifecycle cue:
    money-only text is budget evidence; a broad report without cues is
    background material; anything else is honestly unclear. Conservative by
    design — a missed status is better than a claimed one.
    """
    lower = text.lower()
    for status, cues in _STATUS_RULES:
        for cue in cues:
            idx = lower.find(cue)
            if idx != -1:
                return status, _sentence_around(text, idx, idx + len(cue))
    if has_money:
        return Status.BUDGET, None
    if is_report:
        return Status.BACKGROUND, None
    return Status.UNKNOWN, None
