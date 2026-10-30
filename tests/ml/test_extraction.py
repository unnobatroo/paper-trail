"""extraction + receipt invariants"""

import pytest
from pydantic import ValidationError

from paper_trail.domain.models import DocumentPage, PolicyCandidate
from paper_trail.ml.extraction import NoExtractor, excerpt_found
from tests.profiles import HU


def test_candidate_requires_page_and_excerpt():
    with pytest.raises(ValidationError):
        PolicyCandidate(document_id=1, text="t", normalized_title="t",
                        source_page=0, source_excerpt="x")
    with pytest.raises(ValidationError):
        PolicyCandidate(document_id=1, text="t", normalized_title="t",
                        source_page=3, source_excerpt="")


def test_excerpt_found_requires_raw_verbatim_receipt():
    assert excerpt_found("a  b\nc", "a  b\nc")
    assert not excerpt_found("a  b\nc", "a b c")
    assert not excerpt_found("a b c", "")
    assert not excerpt_found("a b c", "a b d")


@pytest.mark.parametrize("model,thinking_off", [("Qwen/Qwen3-4B-AWQ", True), ("gemma3", False)])
def test_llm_turns_off_qwen3_thinking_and_keeps_only_verbatim_receipts(
        monkeypatch, model, thinking_off):
    from types import SimpleNamespace

    from paper_trail.domain.models import DocumentPage
    from paper_trail.ml.extraction import LLMExtractor
    sent = {}
    reply = ('{"items": ['
             '{"page": 1, "type": "target", "text": "t", "normalized_title": "t",'
             ' "excerpt": "2030-ra 40%-kal csökken"},'
             '{"page": 1, "type": "target", "text": "x", "normalized_title": "x",'
             ' "excerpt": "nincs az oldalon"}]}')

    def create(extra_body=None, **request):
        sent.update(request, **(extra_body or {}))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    page = DocumentPage(page_number=1, text="A kibocsátás 2030-ra 40%-kal csökken.")
    found = LLMExtractor(client, model, HU, window=1).extract([page])
    assert ("chat_template_kwargs" in sent) is thinking_off
    assert [c.source_excerpt for c in found] == ["2030-ra 40%-kal csökken"]


def test_lead_code_comes_off_the_title():
    from paper_trail.ml.extraction import lead_code
    assert [lead_code(t) for t in ("M1.1.2 Távhő", "Ks1: szabályok", "Má-1 ÜHG", "Ms-3",
                                   "2030-ra csökken", "Távhő fejlesztése", "A1. cél",
                                   "1.01 Carbon roadmap", "2030 target")] == [
        "M1.1.2", "Ks1", "Má-1", "Ms-3", None, None, "A1", "1.01", None]


def test_profile_roundtrips_and_no_llm_finds_nothing():
    from paper_trail.ml.lang import LanguageProfile
    assert LanguageProfile.from_dict(HU.to_dict()) == HU
    assert NoExtractor().extract([DocumentPage(page_number=1, text="M1.2 Zöld középületek")]) == []


def test_dense_page_that_blows_the_token_budget_gets_asked_in_halves():
    from paper_trail.domain.models import DocumentPage
    from paper_trail.ml.extraction import LLMExtractor, _Item, _Reply
    page = DocumentPage(page_number=7, text="Fák ültetése a parkban.\nNapelemek az iskolákon.")
    asked = []

    def ask(pages):
        asked.append(pages[0].text)
        if "\n" in pages[0].text:
            return None  # whole page: json cut off at max_tokens
        line = pages[0].text.rstrip(".")
        return _Reply(items=[_Item(type="measure", normalized_title=line, text=line,
                                   page=7, excerpt=line)])
    ex = LLMExtractor(None, "fake", HU, window=1)
    ex._ask = ask
    found = ex.extract([page])
    assert asked == [page.text, "Fák ültetése a parkban.", "Napelemek az iskolákon."]
    # receipts checked against the full page, both halves count
    assert [c.source_excerpt for c in found] == ["Fák ültetése a parkban", "Napelemek az iskolákon"]


def test_receipt_survives_pdf_spaces_inside_words():
    from paper_trail.ml.extraction import source_excerpt
    page = "a fejlesztések bizonyít ékalapú \ntervezése érdekében, létr e hozza"
    # the model quotes the clean words, the page keeps its broken ones
    assert source_excerpt(page, "bizonyítékalapú tervezése") == "bizonyít ékalapú \ntervezése"
    assert source_excerpt(page, "létre hozza") == "létr e hozza"
    assert source_excerpt(page, "napelemek") is None and source_excerpt(page, "  ") is None


def test_title_code_must_be_on_the_page():
    from paper_trail.ml.extraction import grounded_title
    page = "1.01 Carbon neutral roadmap for the city. Develop pathways."
    # invented prefix: code goes, the name stays
    assert grounded_title("M1.01 Carbon neutral roadmap", "t", page) == (
        "Carbon neutral roadmap", None)
    # bare made-up code, nothing left: fall back to the text
    assert grounded_title("M1.01", "Develop pathways for the city", page) == (
        "Develop pathways for the city", None)
    assert grounded_title("1.01 Carbon neutral roadmap", "t", page) == (
        "1.01 Carbon neutral roadmap", "1.01")
    assert grounded_title("Roadmap", "t", page) == ("Roadmap", None)


def _cand(page, quote, title="t"):
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import PolicyCandidate
    return PolicyCandidate(document_id=0, suggested_type=CandidateType.MEASURE, text="t",
                           normalized_title=title, source_page=page, source_excerpt=quote,
                           excerpt_on_page=True)


def test_dedupe_drops_the_same_passage_twice_on_a_page():
    from paper_trail.ml.extraction import dedupe
    a = _cand(1, "Install green roofs on four primary schools by 2027.")
    again = _cand(1, "green roofs on four primary schools by 2027", title="other")
    elsewhere = _cand(2, "Install green roofs on four primary schools by 2027.")
    different = _cand(1, "Plant 500 street trees in the district.")
    # same wording, other numbers: two commitments, both go to review
    two = _cand(1, "Plant 200 street trees in the district by 2027.")
    five = _cand(1, "Plant 500 street trees in the district by 2027.")
    assert dedupe([a, again, elsewhere, different]) == [a, elsewhere, different]
    assert dedupe([two, five]) == [two, five]
    # a shorter quote of the same passage still merges
    assert dedupe([two, _cand(1, "Plant 200 street trees")]) == [two]


def test_fact_sheet_rows_are_not_commitments():
    from paper_trail.ml.extraction import form_row
    labels = HU.form_labels
    assert labels, "hu profile should carry its fact-sheet labels"
    for junk in ("Időtáv 2021-2030", "Felelős: Önkormányzat, helyi civil szervezetek",
                 "Mitigációs célkitűzés kódja Adaptációs célkitűzés kódja Ms-1.3 As-1.2",
                 "• Lehetséges forrás VMOP, ZIKOP, TOP Plusz"):
        assert form_row(junk, labels), junk
    for real in ("Zöldtető alkalmazására pilot projektet kell tervezni 2025-ig.",
                 "Az önkormányzat felelős a fasorok gondozásáért és bővítéséért."):
        assert not form_row(real, labels), real
    # no labels in the profile = rule off
    assert not form_row("Időtáv 2021-2030", ())
