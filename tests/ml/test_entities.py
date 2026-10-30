"""deterministic money, dates, orgs, places, status"""

from paper_trail.domain.enums import BudgetKind, Status
from paper_trail.ml import entities
from tests.profiles import HU


def test_money_kinds_stay_distinct():
    est = entities.extract_money(
        "A beruházás becsült költsége 120 millió Ft.", HU)
    assert est[0].kind == BudgetKind.ESTIMATED_COST
    assert est[0].amount_huf == 120_000_000

    alloc = entities.extract_money(
        "A projekt 2,5 milliárd Ft vissza nem térítendő támogatást nyert.",
        HU)
    assert alloc[0].kind == BudgetKind.INITIAL_APPROPRIATION
    assert alloc[0].amount_huf == 2_500_000_000

    spent = entities.extract_money(
        "A munkálatokra eddig 4 millió Ft kifizetésre került.", HU)
    assert spent[0].kind == BudgetKind.REPORTED_EXPENDITURE


def test_ambiguous_money_stays_unclassified():
    mentions = entities.extract_money(
        "A program értéke 300 000 Ft.", HU)
    assert mentions[0].kind is None
    assert mentions[0].amount_huf == 300_000


def test_hungarian_number_separators():
    # '.' and ' ' are thousand separators; ',' is the decimal mark
    m = entities.extract_money("A keretösszeg 300.000 forint.", HU)
    assert m[0].amount_huf == 300_000
    m = entities.extract_money("881.101 Ft kifizetésre került.", HU)
    assert m[0].amount_huf == 881_101


def test_dates_and_places():
    text = "2024. március 15-én a Losonci téren és a Bérkocsis utcában."
    dates = entities.extract_dates(text, HU)
    assert any("2024" in d for d in dates)
    locs = entities.extract_locations(text, HU)
    assert any("Losonci" in l for l in locs)
    assert any("Bérkocsis" in l for l in locs)


def test_organisations():
    orgs = entities.extract_organisations(
        "A RÉV8 Zrt. és a Józsefvárosi Önkormányzat közreműködésével.", HU
    )
    joined = " ".join(orgs)
    assert "RÉV8" in joined
    assert "Önkormányzat" in joined


def test_classify_status():
    status, excerpt = entities.classify_status(
        "A felújított tér 2023-ban elkészült és átadásra került.", HU
    )
    assert status == Status.COMPLETED
    assert excerpt

    status, _ = entities.classify_status(
        "Az elmúlt évben több mint 100 új kerékpártámasz jött létre.", HU)
    assert status == Status.IN_IMPLEMENTATION or status == Status.COMPLETED

    status, _ = entities.classify_status("Nincs itt semmi releváns.", HU)
    assert status == Status.UNKNOWN

    status, _ = entities.classify_status(
        "A klímastratégia összefoglalja a kerület helyzetét.", HU,
        is_report=True)
    assert status == Status.BACKGROUND

    status, _ = entities.classify_status(
        "A beruházás becsült költsége 120 millió Ft.", HU, has_money=True)
    assert status == Status.BUDGET


def test_gliner_ner_buckets_and_dedupes(monkeypatch):
    from paper_trail.ml.ner import GlinerNer
    ner = GlinerNer()
    fake = [{"label": "organization", "text": "RÉV8 Zrt."},
            {"label": "organization", "text": "rév8 zrt."},
            {"label": "street, square or park", "text": "Losonci téren"},
            {"label": "date", "text": "2024. március 15-én"}]
    # stub the model, the real one is a 1 gb download
    model = type("M", (), {"predict_entities": lambda *a, **k: fake})()
    monkeypatch.setattr(GlinerNer, "_model", model)
    found = ner.find("x")
    assert (found.orgs, found.places, found.dates) == (
        ["RÉV8 Zrt."], ["Losonci téren"], ["2024. március 15-én"])
