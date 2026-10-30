"""extraction + receipt invariants"""

import pytest
from pydantic import ValidationError

from paper_trail.domain.enums import CandidateType
from paper_trail.domain.models import DocumentPage, PolicyCandidate
from paper_trail.ml.extraction import RuleBasedExtractor, excerpt_found
from paper_trail.sources.pdf import read_pages
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


def test_rule_extractor_real_pdf(strategy_pdf):
    pages = read_pages(strategy_pdf)
    candidates = RuleBasedExtractor(HU).extract(pages)

    assert len(candidates) >= 10
    # every candidate has a real page and a verbatim excerpt on it
    for c in candidates:
        assert c.source_page >= 1
        assert c.source_excerpt
        assert excerpt_found(pages[c.source_page - 1].text, c.source_excerpt), (
            c.normalized_title
        )

    measures = [c for c in candidates if c.suggested_type == CandidateType.MEASURE]
    codes = {c.code for c in measures}
    assert "A1.1.1" in codes  # Utca újra-tervezési, zöldítési program
    assert any(c.responsible_org for c in measures)


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


def test_hybrid_keeps_rules_and_adds_only_new_llm_items():
    from paper_trail.ml.extraction import Extractor, HybridExtractor

    def cand(page, title, text):
        return PolicyCandidate(document_id=0, suggested_type=CandidateType.MEASURE, text=text,
                               normalized_title=title, source_page=page, source_excerpt=text,
                               excerpt_on_page=True)

    class Fixed(Extractor):
        def __init__(self, items):
            self.items = items

        def extract(self, pages):
            return list(self.items)
    rules = Fixed([cand(20, "M1.2 Zöld középületek", "M1.2 Zöld középületek")])
    llm = Fixed([cand(20, "M1.2 Zöld középületek", "Zöld középületek kialakítása"),
                 cand(20, "Fasor minden utcában", "Minden utcában legyen fasor"),
                 cand(21, "M1.2 Zöld középületek", "más oldal")])
    titles = [(c.source_page, c.normalized_title)
              for c in HybridExtractor(rules, llm).extract([])]
    assert titles == [(20, "M1.2 Zöld középületek"), (20, "Fasor minden utcában"),
                      (21, "M1.2 Zöld középületek")]


def test_profile_roundtrips_and_empty_finds_nothing():
    from paper_trail.ml.lang import LanguageProfile
    assert LanguageProfile.from_dict(HU.to_dict()) == HU
    empty = LanguageProfile.empty("hu")
    assert RuleBasedExtractor(empty).extract(
        [DocumentPage(page_number=1, text="M1.2 Zöld középületek")]) == []
