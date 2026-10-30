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


def test_profile_roundtrips_and_no_llm_finds_nothing():
    from paper_trail.ml.lang import LanguageProfile
    assert LanguageProfile.from_dict(HU.to_dict()) == HU
    assert NoExtractor().extract([DocumentPage(page_number=1, text="M1.2 Zöld középületek")]) == []
