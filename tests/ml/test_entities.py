"""deterministic money, years, status"""

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


def test_big_decimal_amounts_stay_exact():
    # float made this 4 099 999 999
    assert entities.extract_money("A keret 4,1 milliárd Ft.", HU)[0].amount_huf == 4_100_000_000


def test_years_and_place_base_form():
    assert entities.years("2024. március 15-én, 2030-ra, 1999 és 2024") == ["2024", "2030", "1999"]
    # inflections fold together so passages and commitments meet
    assert (entities.norm_place("Bérkocsis utcában", HU)
            == entities.norm_place("Bérkocsis utcája", HU) == "bérkocsis utcá")


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
    model = type("M", (), {"inference": lambda self, chunks, *a, **k: [fake for _ in chunks]})()
    monkeypatch.setattr(GlinerNer, "_model", model)
    found = ner.find("x")
    assert (found.orgs, found.places, found.dates) == (
        ["RÉV8 Zrt."], ["Losonci téren"], ["2024. március 15-én"])
    # bare years ride along, matching compares those
    assert ner.find("terv 2030-ra").dates == ["2024. március 15-én", "2030"]
    assert ner.find("   ").orgs == []


def test_gliner_chunks_split_on_words_and_cover_everything():
    from paper_trail.ml.ner import _chunks
    text = " ".join(f"szó{i}" for i in range(500))
    chunks = _chunks(text, 100)
    assert all(len(c) <= 100 for c in chunks)
    assert " ".join(chunks) == text and _chunks("", 100) == []


def test_no_ner_keeps_only_years():
    from paper_trail.ml.ner import NoNer, get_ner
    assert get_ner("none").find("A RÉV8 Zrt. 2024-ben").__dict__ == {
        "orgs": [], "places": [], "dates": ["2024"]}
    assert isinstance(get_ner("none"), NoNer)
