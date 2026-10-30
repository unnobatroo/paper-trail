import importlib.util
from pathlib import Path

from paper_trail.domain.models import DocumentPage
from paper_trail.ml.extraction import LLMExtractor, _Item, _Reply
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
    extractor._ask = lambda window: _Reply(items=[_Item(
        type="measure", normalized_title="M1.1.2 Távhőszolgáltatás fejlesztése",
        text="Távhőszolgáltatás fejlesztése", page=3, excerpt="Távhőszolgáltatás fejlesztése")])
    golds = [{"page": 3, "title": "Távhőszolgáltatás fejlesztése", "code": "M1.1.2"},
             {"page": 3, "title": "Napelemek az iskolákon", "code": "M1.1.9"}]
    out = eval_extraction.score_doc(extractor, Path("x.pdf"), golds)
    assert (out["found"], out["recall"], out["returned"]) == (1, 0.5, 1)
    assert (out["precision"], out["f1"]) == (1.0, 0.667)
    assert out["missed"] == [{"page": 3, "title": "Napelemek az iskolákon"}]
    assert out["answers"] == [{"page": 3, "type": "measure",
                               "title": "M1.1.2 Távhőszolgáltatás fejlesztése",
                               "excerpt": "Távhőszolgáltatás fejlesztése"}]


def test_gate_ships_only_on_holdout_gain(capsys):
    base = {"summary": {"recall_macro_holdout": 0.5},
            "docs": {"a": {"recall": 0.9, "split": "train"},
                     "b": {"recall": 0.5, "split": "holdout"}}}
    # train doc jumps, holdout drops: that's overfitting, no ship
    worse = {"a": {"recall": 1.0, "split": "train"}, "b": {"recall": 0.4, "split": "holdout"}}
    assert eval_extraction.gate(base, {"recall_macro_holdout": 0.4}, worse) == 1
    assert "NO SHIP" in capsys.readouterr().out
    better = {"b": {"recall": 0.6, "split": "holdout"}}
    assert eval_extraction.gate(base, {"recall_macro_holdout": 0.6}, better) == 0
    # hard holdout doc swapped for an easy one: higher macro, but not comparable
    swapped = {"c": {"recall": 0.9, "split": "holdout"}}
    assert eval_extraction.gate(base, {"recall_macro_holdout": 0.9}, swapped) == 1


def test_same_quote_matches_even_with_a_useless_title():
    from types import SimpleNamespace
    gold = {"title": "Carbon Literacy training – decision makers", "code": "1.02",
            "quote": "Provide ‘carbon literacy’ training to key decision-makers in the council."}
    cand = SimpleNamespace(text="x", normalized_title="M1.02", source_excerpt=(
        "Provide ‘carbon literacy’ training to key decision-makers in the council."))
    assert eval_extraction.matches(gold, cand)
    # sharing a few common words isn't the same passage
    other = SimpleNamespace(text="x", normalized_title="M1.03",
                            source_excerpt="Establish a climate emergency board in the council.")
    assert not eval_extraction.matches(gold, other)
