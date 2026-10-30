import importlib.util
import json
from pathlib import Path

from paper_trail.domain.enums import CandidateType, ReviewStatus
from paper_trail.domain.models import DocumentPage, PolicyCandidate, SourceDocument
from paper_trail.repositories.store import PolicyRepository
from tests.profiles import HU

_spec = importlib.util.spec_from_file_location(
    "build_dataset",
    Path(__file__).resolve().parents[2] / "scripts" / "ml" / "finetune" / "build_dataset.py")
build_dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_dataset)


def test_only_human_decisions_become_labels(dsn, monkeypatch):
    repo = PolicyRepository(dsn)
    doc = repo.add_document(SourceDocument(title="t", publisher="p"))

    def cand(page, text, status):
        cid = repo.add_candidate(PolicyCandidate(
            document_id=doc, suggested_type=CandidateType.MEASURE, text=text,
            normalized_title=text, source_page=page, source_excerpt=text, excerpt_on_page=True))
        repo.set_candidate_status(cid, status)
    cand(1, "Fák ültetése", ReviewStatus.ACCEPTED)
    cand(1, "Bevezetés", ReviewStatus.REJECTED)
    cand(2, "Tartalomjegyzék", ReviewStatus.REJECTED)
    cand(3, "Napelemek", ReviewStatus.UNREVIEWED)
    # half-reviewed page: its answer would leave out the open one
    cand(4, "Zöldtető", ReviewStatus.ACCEPTED)
    cand(4, "Esővíz", ReviewStatus.UNREVIEWED)
    # accepted, but the quote sits past the prompt's page cut
    cand(5, "Fasor", ReviewStatus.ACCEPTED)
    texts = {1: "Fák ültetése", 2: "page 2", 3: "Napelemek", 4: "Zöldtető Esővíz",
             5: "x" * 6000 + " Fasor"}
    pages = [DocumentPage(page_number=n, text=t) for n, t in texts.items()]
    monkeypatch.setattr(build_dataset, "read_pages", lambda _: pages)

    rows = build_dataset.examples(repo, HU, doc, Path("x.pdf"))
    answers = {r["page"]: json.loads(r["messages"][1]["content"])["items"] for r in rows}
    # accepted -> an item, rejects-only -> empty, unreviewed page -> not a label at all
    assert [i["normalized_title"] for i in answers[1]] == ["Fák ültetése"]
    assert answers[2] == [] and 3 not in answers and 4 not in answers
    assert answers[5] == []


def test_gold_only_trains_on_train_split(tmp_path, monkeypatch):
    pages = [DocumentPage(page_number=1, text="a fák ültetése"),
             DocumentPage(page_number=2, text="page 2")]
    monkeypatch.setattr(build_dataset, "read_pages", lambda _: pages)
    profiles = Path(__file__).resolve().parents[1] / "fixtures" / "profiles"
    rows = [
        {"doc": "a", "pdf": "a.pdf", "lang": "hu", "split": "train", "page": 1,
         "kind": "measure", "title": "Fák", "quote": "fák ültetése"},
        {"doc": "a", "pdf": "a.pdf", "lang": "hu", "split": "train", "page": 2, "empty": True},
        {"doc": "b", "pdf": "b.pdf", "lang": "hu", "split": "holdout", "page": 1,
         "kind": "measure", "title": "x", "quote": "x"},
        # page the pdf doesn't have: skipped, not a KeyError
        {"doc": "a", "pdf": "a.pdf", "lang": "hu", "split": "train", "page": 9,
         "kind": "measure", "title": "y", "quote": "y"},
    ]
    out = build_dataset.gold_examples(rows, tmp_path, profiles)
    answers = {(r["doc"], r["page"]): json.loads(r["messages"][1]["content"])["items"] for r in out}
    assert answers == {("a", 1): [{"type": "measure", "normalized_title": "Fák",
                                   "text": "fák ültetése", "page": 1,
                                   "excerpt": "fák ültetése"}], ("a", 2): []}
