import importlib.util
from pathlib import Path

from paper_trail.domain.models import DocumentPage
from paper_trail.ml.extraction import LLMExtractor, _LLMItem, _LLMResponse
from tests.profiles import HU

_spec = importlib.util.spec_from_file_location(
    "eval_extraction",
    Path(__file__).resolve().parents[2] / "scripts" / "ml" / "eval_extraction.py")
eval_extraction = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_extraction)


def test_score_doc_counts_hits_and_misses_per_page(monkeypatch):
    page = DocumentPage(page_number=3, text="M1.1.2 Távhőszolgáltatás fejlesztése a kerületben.")
    monkeypatch.setattr(eval_extraction, "read_pages", lambda _: [page])
    extractor = LLMExtractor(None, "fake", HU, window=1)
    # stub the model: one right answer, nothing for the second gold row
    extractor._ask = lambda window: _LLMResponse(items=[_LLMItem(
        type="measure", normalized_title="M1.1.2 Távhőszolgáltatás fejlesztése",
        text="Távhőszolgáltatás fejlesztése", page=3, excerpt="Távhőszolgáltatás fejlesztése")])
    golds = [{"page": 3, "title": "Távhőszolgáltatás fejlesztése", "code": "M1.1.2"},
             {"page": 3, "title": "Napelemek az iskolákon", "code": "M1.1.9"}]
    out = eval_extraction.score_doc(extractor, Path("x.pdf"), golds)
    assert (out["found"], out["recall"], out["returned"]) == (1, 0.5, 1)
    assert out["missed"] == [{"page": 3, "title": "Napelemek az iskolákon"}]
