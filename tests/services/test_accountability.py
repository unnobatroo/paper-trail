"""audit loopholes: umbrella contracts, zombie tenders, budget states, jurisdiction,
parcel aliases and maintenance posing as climate action"""
from types import SimpleNamespace

from paper_trail.domain.enums import (
    BudgetKind,
    CandidateType,
    EvidenceFlag,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
)
from paper_trail.domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    OfficialSource,
    PolicyCandidate,
    SourceDocument,
)
from paper_trail.ml import entities
from paper_trail.ml.accountability import FinancialAuditor, PassageAuditor
from paper_trail.ml.embeddings import HashingProvider
from paper_trail.services.evidence_service import EvidenceService
from paper_trail.services.metrics_service import MetricsService, with_effective_flags
from paper_trail.services.review_service import ReviewService
from paper_trail.sources.fetch import FetchedPage
from tests.profiles import HU

AUDIT = PassageAuditor(HU)
MONEY = FinancialAuditor(HU)


def test_ids_parcels_and_polarity_come_from_the_passage():
    text = ("A Kálvária tér (36542/1 hrsz.) felújítása az EKR001234562021 eljárásban. "
            "A VEKOP-6.2.1-15-2016-00001 projekt támogatási szerződése.")
    assert AUDIT.procurement_ids(text) == ["EKR001234562021", "VEKOP-6.2.1-15-2016-00001"]
    assert AUDIT.parcels(text) == ["36542/1"]
    assert AUDIT.parcels("hrsz.: 35012/4 alatti ingatlan") == ["35012/4"]
    assert AUDIT.polarity("A szerződést a kivitelező felmondta.") == EvidencePolarity.TERMINATION
    assert AUDIT.polarity("Szerződésmódosítás: a határidő 2026.") == EvidencePolarity.AMENDMENT
    assert AUDIT.polarity("Átadták a felújított teret.") == EvidencePolarity.AFFIRMATIVE


def test_maintenance_without_upgrade_is_suspect_and_capped():
    flags = AUDIT.flags("Csőtörés javítás és kátyúzás a Práter utcában.")
    assert flags == [EvidenceFlag.MAINTENANCE_ONLY_SUSPECT]
    assert AUDIT.flags("Csőtörés után a teljes vezetékcsere megtörtént.") == []
    rel, reasons = PassageAuditor.cap(RelationshipType.DIRECT_IMPLEMENTATION, [], flags)
    assert rel == RelationshipType.INDIRECT and "maintenance" in reasons[0]
    # an unrelated hint is never raised by a cap
    assert PassageAuditor.cap(RelationshipType.UNRELATED, [], flags)[0] == (
        RelationshipType.UNRELATED)


def test_jurisdiction_follows_the_asset_owner():
    assert AUDIT.jurisdiction("Ivóvíz-hálózat rekonstrukciója") == (
        Jurisdiction.PUBLIC_UTILITY_WATER)
    assert AUDIT.jurisdiction("Távhő hőközpontok korszerűsítése") == (
        Jurisdiction.PUBLIC_UTILITY_HEATING)
    assert AUDIT.jurisdiction("Fasor a Népszínház utcában") == (
        Jurisdiction.DISTRICT_MUNICIPALITY)


def test_budget_states_are_classified_in_order():
    kind = lambda s: entities.extract_money(s, HU)[0].kind  # noqa: E731
    assert kind("A zárszámadás szerint 80 millió Ft tényleges kiadás.") == (
        BudgetKind.ACTUAL_EXPENDITURE)
    assert kind("A módosított előirányzat 90 millió Ft.") == BudgetKind.AMENDED_APPROPRIATION
    assert kind("Az eredeti előirányzat 100 millió Ft.") == BudgetKind.INITIAL_APPROPRIATION
    assert kind("A szerződéses ár nettó 95 millió Ft.") == BudgetKind.CONTRACTED_PRICE
    assert BudgetKind("approved_allocation") == BudgetKind.INITIAL_APPROPRIATION


def _budget(kind, amount, year=2024):
    return BudgetRecord(evidence_id=1, kind=kind, amount_huf=amount,
                        amount_native=str(amount), fiscal_year=year)


def test_appropriation_is_not_spending_until_final_accounts():
    plain = EvidenceItem(commitment_id=1, url="u", title="t", snippet="")
    money = MONEY.summarize([_budget(BudgetKind.INITIAL_APPROPRIATION, 100_000_000),
                                   _budget(BudgetKind.REPORTED_EXPENDITURE, 90_000_000)],
                                  [plain])
    assert not money.executed
    assert any("final accounts" in f for f in money.findings)
    money = MONEY.summarize([_budget(BudgetKind.INITIAL_APPROPRIATION, 100_000_000),
                                   _budget(BudgetKind.AMENDED_APPROPRIATION, 70_000_000),
                                   _budget(BudgetKind.ACTUAL_EXPENDITURE, 60_000_000)],
                                  [plain])
    assert money.executed
    # the amended figure is the one compared, kinds are never added up
    assert any("10 000 000 HUF" in f and "60 000 000 of 70 000 000" in f
               for f in money.findings)
    signed = EvidenceItem(commitment_id=1, url="u", title="t",
                          snippet="A műszaki átadás-átvételi jegyzőkönyv aláírva.")
    assert MONEY.summarize([], [signed]).executed


def _service(evidence, tmp_path, pages):
    svc = EvidenceService(evidence, SimpleNamespace(search=lambda *a, **kw: []),
                          HashingProvider(), cache_dir=tmp_path, profile=HU)
    svc._collect_urls = lambda *a: [p.url for p in pages]
    svc._fetch_page = lambda url, *a: next(p for p in pages if p.url == url)
    return svc


def _commitment(policy, title):
    com = Commitment(kind=CandidateType.MEASURE, title=title)
    com.id = policy.add_commitment(com)
    return com


def test_umbrella_contract_cancellation_reaches_every_commitment(policy, evidence, tmp_path):
    framework = FetchedPage("https://jozsefvaros.hu/ekr", "Keretszerződés",
                            "Vízvezeték rekonstrukció 45 utcában, EKR001234562021.")
    cancelled = FetchedPage("https://jozsefvaros.hu/felmondas", "Felmondás",
                            "Az EKR001234562021 szerződést az önkormányzat felmondta.")
    first, second = _commitment(policy, "Vízvezeték A"), _commitment(policy, "Vízvezeték B")
    svc = _service(evidence, tmp_path, [framework, cancelled])
    svc._rank = lambda com, pages: [(framework, framework.text, 0.9)]
    [link_a] = svc.find_evidence(first)
    # a person accepts the first link before anyone notices the cancellation
    evidence.decide_link(link_a.id, ReviewStatus.ACCEPTED, RelationshipType.DIRECT_IMPLEMENTATION)
    svc._rank = lambda com, pages: [(cancelled, cancelled.text, 0.9)]
    [link_b] = svc.find_evidence(second)
    assert link_b.suggested_relationship != RelationshipType.DIRECT_IMPLEMENTATION
    ev_map = evidence.evidence_many([link_a.evidence_id, link_b.evidence_id])
    assert ev_map[link_b.evidence_id].polarity == EvidencePolarity.TERMINATION
    with_effective_flags(evidence, ev_map)
    # the accepted evidence now carries the warning, and its own row was never rewritten
    assert EvidenceFlag.REGRESSION_WARNING in ev_map[link_a.evidence_id].flags
    assert evidence.link(link_a.id).review_status == ReviewStatus.ACCEPTED
    row = next(r for r in MetricsService(policy, evidence, HU).trail()
               if r.commitment.id == first.id)
    assert any("cancelled" in f for f in row.findings)
    assert row.status.value == "unknown"


def test_parcel_numbers_resolve_to_the_street_that_matching_sees(policy, evidence, tmp_path):
    evidence.upsert_place("square", "Kálvária tér", "Kálvária tér", "VIII. kerület",
                          None, None, "osm")
    first = FetchedPage("https://jozsefvaros.hu/a", "Terv",
                        "A Kálvária tér 36542/1 hrsz. zöldfelületének rekonstrukciója.")
    contract = FetchedPage("https://jozsefvaros.hu/b", "Szerződés",
                           "A 36542/1 hrsz. ingatlan felújítása elkészült.")
    com = _commitment(policy, "Kálvária tér megújítása")
    svc = _service(evidence, tmp_path, [first, contract])
    svc._rank = lambda c, pages: [(first, first.text, 0.5)]
    svc.find_evidence(com)
    assert evidence.resolve_parcel("36542/1") == "Kálvária tér"
    svc._rank = lambda c, pages: [(contract, contract.text, 0.5)]
    [link] = svc.find_evidence(com)
    # the contract never names the square, the gazetteer adds it
    assert "Kálvária tér" in evidence.evidence(link.evidence_id).locations


def test_accepting_suggests_a_jurisdiction_the_reviewer_can_change(policy, evidence):
    doc_id = policy.add_document(SourceDocument(title="Stratégia", publisher="Önk."))
    cid = policy.add_candidate(PolicyCandidate(
        document_id=doc_id, suggested_type=CandidateType.MEASURE,
        text="Távhő hőközpontok korszerűsítése", normalized_title="Távhő",
        source_page=1, source_excerpt="Távhő hőközpontok korszerűsítése",
        excerpt_on_page=True))
    review = ReviewService(policy, evidence, HU)
    com_id = review.accept_candidate(cid)
    assert policy.commitment(com_id).asset_owner_jurisdiction == (
        Jurisdiction.PUBLIC_UTILITY_HEATING)
    review.set_jurisdiction(com_id, Jurisdiction.METROPOLITAN_MUNICIPALITY)
    assert policy.commitment(com_id).asset_owner_jurisdiction == (
        Jurisdiction.METROPOLITAN_MUNICIPALITY)


def test_routed_owner_domains_come_from_the_registry(evidence, tmp_path):
    evidence.upsert_official_source(OfficialSource(
        url="https://www.vizmuvek.hu/hu/beruhazasok", publisher="Fővárosi Vízművek",
        jurisdiction=Jurisdiction.PUBLIC_UTILITY_WATER))
    evidence.upsert_official_source(OfficialSource(
        url="https://www.fotav.hu/fejlesztesek", publisher="Főtáv",
        jurisdiction=Jurisdiction.PUBLIC_UTILITY_HEATING))
    queries = []
    search = SimpleNamespace(search=lambda q, **kw: queries.append(q) or [])
    svc = EvidenceService(evidence, search, HashingProvider(), cache_dir=tmp_path,
                          profile=HU, allowed_domains=("jozsefvaros.hu",))
    svc._fetch_page = lambda *a: None
    com = Commitment(id=1, kind=CandidateType.MEASURE, title="Ivóvízhálózat",
                     asset_owner_jurisdiction=Jurisdiction.PUBLIC_UTILITY_WATER)
    svc.find_evidence(com)
    assert "site:jozsefvaros.hu Ivóvízhálózat" in queries
    assert "site:www.vizmuvek.hu Ivóvízhálózat Fővárosi Vízművek" in queries
    # another owner's sites are not searched for this commitment
    assert not any("fotav" in q for q in queries)
    # a crawler re-upsert without an owner keeps the stored one
    evidence.upsert_official_source(OfficialSource(url="https://www.vizmuvek.hu/hu/beruhazasok"))
    assert {s.url: s.jurisdiction for s in evidence.official_sources()}[
        "https://www.vizmuvek.hu/hu/beruhazasok"] == Jurisdiction.PUBLIC_UTILITY_WATER
