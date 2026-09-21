"""Extraction and provenance invariants."""

import pytest
from pydantic import ValidationError

from paper_trail.domain.enums import CandidateType
from paper_trail.domain.models import PolicyCandidate
from paper_trail.ml.extraction import RuleBasedExtractor, excerpt_found
from paper_trail.sources.pdf import read_pages


def test_candidate_requires_page_and_excerpt():
    with pytest.raises(ValidationError):
        PolicyCandidate(document_id=1, text="t", normalized_title="t",
                        source_page=0, source_excerpt="x")
    with pytest.raises(ValidationError):
        PolicyCandidate(document_id=1, text="t", normalized_title="t",
                        source_page=3, source_excerpt="")


def test_excerpt_found_normalises_whitespace():
    assert excerpt_found("a  b\nc", "a b c")
    assert not excerpt_found("a b c", "a b d")


def test_rule_extractor_real_pdf(strategy_pdf):
    pages = read_pages(strategy_pdf)
    candidates = RuleBasedExtractor().extract(pages)

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
