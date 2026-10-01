"""Language profiles — every locale-specific word list and document label
the deterministic parsers need, as data tables selected by
PAPER_TRAIL_LANGUAGE at startup.

The algorithm modules (`entities`, `extraction`, `evidence_service`) hold
no literals: they compile their patterns from the profile they are handed.
A new deployment language = a new entry in `PROFILES`, nothing else.

Registry-of-record note: the source catalogue (URLs/publishers) is *not*
here — that is application data and lives in the `official_sources` table.
These are linguistic resources, the same category as gettext catalogs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import BudgetKind, Status


@dataclass(frozen=True)
class LanguageProfile:
    """One locale's cue tables. All string tuples are matched
    case-insensitively against lowered text unless noted."""

    code: str                     # ISO-ish tag, e.g. "hu"
    name: str                     # "Hungarian" — used in LLM prompts
    stemmer: str                  # py_rust_stemmers / Snowball language
    ts_config: str                # Postgres regconfig for tsvector columns

    # money
    currency_words: tuple[str, ...] = ()        # ("Ft", "forint")
    multiplier_words: dict[str, int] = field(default_factory=dict)
    decimal_comma: bool = False                 # "2,5" = 2.5
    budget_cues: dict[BudgetKind, tuple[str, ...]] = field(
        default_factory=dict)

    # dates
    months_re: str = ""           # alternation of month names

    # organisations / locations
    upper_chars: str = "A-Z"      # uppercase-start character class body
    lower_chars: str = "a-z"      # word-body lowercase class
    org_suffixes_re: str = ""     # legal-form suffixes (Zrt|Kft|Ltd|…)
    org_names_re: str = ""        # literal known names (alternation)
    place_words_re: str = ""      # tér|utca|park|…
    place_drop_suffixes: tuple[str, ...] = ()   # inflections _norm_place strips

    # document/report classification
    report_cues: tuple[str, ...] = ()
    status_rules: tuple[tuple[Status, tuple[str, ...]], ...] = ()
    title_stopwords: frozenset[str] = frozenset()

    # document-layout extraction (fixed-layout policy PDFs)
    code_pattern: str = r""                     # e.g. [AMS][a-z]?\d+(\.\d+)*
    goal_labels: tuple[str, ...] = ()           # "Stratégiai cél"
    pillar_labels: tuple[str, ...] = ()         # "Tematikus cél"
    card_label: str = ""                        # "Intézkedés kódja"
    responsible_label: str = ""                 # "Felelős"
    timeframe_label: str = ""                   # "Időtáv"
    indicator_label: str = ""                   # "Indikátor"
    noise_words: tuple[str, ...] = ()           # grant codes / furniture
    intent_re: str = ""                         # target-sentence verbs
    units_re: str = ""                          # m2|%|db|fő|mm|°C|kWh|Ft

    def __hash__(self) -> int:  # dict fields are unhashable — key on code
        return hash(self.code)


# ---------------------------------------------------------------------------
# Hungarian — Józsefváros deployment

HU = LanguageProfile(
    code="hu",
    name="Hungarian",
    stemmer="hungarian",
    ts_config="hungarian",
    currency_words=("Ft", "forint"),
    multiplier_words={
        "milliárd": 1_000_000_000, "mrd": 1_000_000_000,
        "millió": 1_000_000, "ezer": 1_000,
    },
    decimal_comma=True,
    budget_cues={
        BudgetKind.ESTIMATED_COST: (
            "becsült", "várható költség", "tervezett költség",
            "előirányzat"),
        BudgetKind.APPROVED_ALLOCATION: (
            "támogatást nyert", "támogatást kap", "elnyert",
            "nyert összeg", "költségkeret", "keretösszeg", "keretből",
            "pályázati keret", "támogatási szerződés", "forint támogatás",
            "forintra", "igényelhető", "megállapított", "jóváhagyott",
            "különített el", "forintot különít"),
        BudgetKind.REPORTED_EXPENDITURE: (
            "kifizetés", "kifizetésre került", "költöttek", "elköltött",
            "elszámolt", "felmerült költség", "került sor"),
    },
    months_re=(
        "január|február|március|április|május|június|július|augusztus|"
        "szeptember|október|november|december"),
    upper_chars="A-ZÁÉÍÓÖŐÚÜŰ",
    lower_chars="a-záéíóöőúüű",
    org_suffixes_re=(
        r"Zrt\.?|Kft\.?|Önkormányzat[a-záéíóöőúüű]*|Iroda|Központ|"
        r"Egyesület|Alapítvány|Hivatal[a-záéíóöőúüű]*"),
    org_names_re=(
        r"RÉV8|Rév8|JGK|FŐKERT|Főkert|BKV|BKK|Józsefvárosi Önkormányzat|"
        r"Budapest Főváros Önkormányzat[a-záéíóöőúüű]*"),
    place_words_re=(
        r"tér|tere|téren|téri|utca|utcában|utcába|utcáján|utcai|út|úton|"
        r"köz|sétány|sétányt|park|parkja|kert|kertje|lakótelep"),
    place_drop_suffixes=("ban", "ba", "ján", "ja", "én", "re", "n", "t",
                         "i", "e"),
    report_cues=(
        ".pdf", "beszámoló", "secap", "stratégia", "akcióterv",
        "tanulmány", "intézkedési terv", "koncepcio", "koncepció",
        "program 20", "program-", "melleklet", "tervezet"),
    status_rules=(
        (Status.COMPLETED, (
            "elkészült", "megvalósult", "átadták", "átadásra került",
            "megújult", "fejeződtek be", "befejeződött", "ültettek el",
            "elültetésre került", "elültették", "ültetésre került",
            "telepítettünk", "létesült", "megnyílt", "jött létre",
            "létrejött", "megépült", "készült el", "megvalósítottuk",
            "megnyitottuk", "átadtuk", "átadását")),
        (Status.IN_IMPLEMENTATION, (
            "kivitelezés folyamatban", "kivitelezése folyamatban",
            "munkálatok", "a munkák megkezdődtek", "munka megkezdődött",
            "felbontjuk", "feltörjük", "megújítása zajlik",
            "felújítás zajlik", "építkezés", "kivitelezés zajlik",
            "kivitelezését")),
        (Status.IN_PREPARATION, (
            "tervezés folyamatban", "előkészítés", "tervezzük",
            "véleményezhetik", "koncepcióterv", "lakossági fórum",
            "kiviteli terv", "engedélyeztetés", "előkészítése folyamatban",
            "közösségi tervezés", "tervezik meg", "egyeztetésre kerül",
            "társadalmi egyeztetés")),
        (Status.ANNOUNCED, (
            "bejelentette", "bejelentés", "kiírjuk", "kiírásra kerül",
            "meghirdette", "meghirdetésre kerül", "pályázatot indít",
            "pályázatot hirdet", "indul a pályázat", "indul a program",
            "pályázni lehet", "nyílt pályázat")),
        (Status.PLANNED, (
            "tervezett", "tervei szerint", "nyertes ötlet", "javaslat",
            "tervezik", "valósuljon meg", "megvalósításra kerül",
            "megvalósítását tervezi")),
    ),
    title_stopwords=frozenset({
        "a", "az", "egy", "és", "hogy", "the", "of", "es", "-", "–",
        "pdf", "letoltes", "downloads"}),
    code_pattern=r"[AMS][a-z]?\d+(?:\.\d+)*",
    goal_labels=("Stratégiai cél",),
    pillar_labels=("Tematikus cél",),
    card_label="Intézkedés kódja",
    responsible_label="Felelős",
    timeframe_label="Időtáv",
    indicator_label="Indikátor",
    noise_words=("KEHOP", "Klímastratégiája"),
    intent_re=(
        r"cél|irányoz|irányít|tervez|növel|csökkent|elér|megvalós|"
        r"felszámol|kialakít|fejleszt|javít|bevezet|biztosít|fenntart|"
        r"ültet|korszerűsít|támogat"),
    units_re=r"m2|m²|%|db|fő/év|fő|mm|°C|kWh|Ft|m-en",
)


# ---------------------------------------------------------------------------
# English — generic municipal/official-document baseline. The rule extractor
# covers common strategy-document phrasing; unusual layouts should use the
# LLM extractor instead.

EN = LanguageProfile(
    code="en",
    name="English",
    stemmer="english",
    ts_config="english",
    currency_words=("EUR", "USD", "GBP", "€", "$", "£",
                    "euros", "dollars", "pounds"),
    multiplier_words={
        "billion": 1_000_000_000, "bn": 1_000_000_000,
        "million": 1_000_000, "m": 1_000_000, "thousand": 1_000,
        "k": 1_000,
    },
    decimal_comma=False,
    budget_cues={
        BudgetKind.ESTIMATED_COST: (
            "estimated cost", "expected cost", "planned cost",
            "projected cost", "budgeted"),
        BudgetKind.APPROVED_ALLOCATION: (
            "approved funding", "granted", "grant of", "allocated",
            "funding approved", "awarded", "budget allocation",
            "funding secured", "earmarked"),
        BudgetKind.REPORTED_EXPENDITURE: (
            "spent", "expenditure", "paid out", "disbursed",
            "cost incurred", "spent to date"),
    },
    months_re=(
        "january|february|march|april|may|june|july|august|september|"
        "october|november|december"),
    org_suffixes_re=(
        r"Ltd\.?|Inc\.?|LLC|Corp\.?|Council|Municipality|Authority|"
        r"Department|Agency|Foundation|Association|Committee|Trust"),
    org_names_re=r"",
    place_words_re=(
        r"street|avenue|road|square|park|boulevard|lane|district|"
        r"neighbourhood|neighborhood|garden|gardens"),
    place_drop_suffixes=(),
    report_cues=(
        ".pdf", "report", "strategy", "action plan", "study", "annex",
        "draft", "plan 20", "framework", "white paper", "consultation"),
    status_rules=(
        (Status.COMPLETED, (
            "completed", "finished", "opened", "delivered", "inaugurated",
            "was built", "has been built", "installed", "planted",
            "implemented", "unveiled")),
        (Status.IN_IMPLEMENTATION, (
            "under construction", "underway", "works are ongoing",
            "construction started", "implementation in progress",
            "being built", "work has begun", "in progress")),
        (Status.IN_PREPARATION, (
            "in planning", "design phase", "under consultation",
            "preparatory work", "permitting", "public consultation",
            "being designed", "in preparation")),
        (Status.ANNOUNCED, (
            "announced", "call for proposals", "tender published",
            "call for tenders", "programme launched", "program launched",
            "applications open", "open call")),
        (Status.PLANNED, (
            "planned", "proposed", "is envisaged", "scheduled",
            "will be implemented", "earmarked for")),
    ),
    title_stopwords=frozenset({
        "a", "an", "the", "of", "and", "for", "in", "on", "to", "-",
        "–", "pdf", "download", "downloads"}),
    code_pattern=r"[A-Z]{1,3}[a-z]?\d+(?:\.\d+)*",
    goal_labels=("Strategic goal", "Strategic objective"),
    pillar_labels=("Thematic objective", "Pillar"),
    card_label="Measure code",
    responsible_label="Responsible",
    timeframe_label="Timeframe",
    indicator_label="Indicator",
    noise_words=("INTERREG", "LIFE-", "ERDF"),
    intent_re=(
        r"aim|target|goal|increase|decrease|reduce|achieve|implement|"
        r"establish|develop|improve|introduce|ensure|maintain|plant|"
        r"upgrade|support|create|deliver"),
    units_re=r"m2|m²|%|km|km2|ha|mm|°C|kWh|MWh|tCO2|EUR|USD|GBP|€|\$|£",
)


PROFILES: dict[str, LanguageProfile] = {"hu": HU, "en": EN}


def get_profile(code: str) -> LanguageProfile:
    """The profile for `code`; unknown codes fall back to `en` (the
    baseline) rather than crashing — a missing profile means the
    deterministic parsers run with generic cues."""
    return PROFILES.get((code or "").lower().split("-")[0], EN)
