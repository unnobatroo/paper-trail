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
    pages = [DocumentPage(page_number=n, text=f"page {n}") for n in (1, 2, 3)]
    monkeypatch.setattr(build_dataset, "read_pages", lambda _: pages)

    rows = build_dataset.examples(repo, HU, doc, Path("x.pdf"))
    answers = {r["page"]: json.loads(r["messages"][1]["content"])["items"] for r in rows}
    # accepted -> an item, rejects-only -> empty, unreviewed page -> not a label at all
    assert [i["normalized_title"] for i in answers[1]] == ["Fák ültetése"]
    assert answers[2] == [] and 3 not in answers


def test_gold_only_trains_on_train_split(tmp_path, monkeypatch):
    pages = [DocumentPage(page_number=n, text=f"page {n}") for n in (1, 2)]
    monkeypatch.setattr(build_dataset, "read_pages", lambda _: pages)
    profiles = Path(__file__).resolve().parents[1] / "fixtures" / "profiles"
    rows = [
        {"doc": "a", "pdf": "a.pdf", "lang": "hu", "split": "train", "page": 1,
         "kind": "measure", "title": "Fák", "quote": "fák ültetése"},
        {"doc": "a", "pdf": "a.pdf", "lang": "hu", "split": "train", "page": 2, "empty": True},
        {"doc": "b", "pdf": "b.pdf", "lang": "hu", "split": "holdout", "page": 1,
         "kind": "measure", "title": "x", "quote": "x"},
    ]
    out = build_dataset.gold_examples(rows, tmp_path, profiles)
    answers = {(r["doc"], r["page"]): json.loads(r["messages"][1]["content"])["items"] for r in out}
    assert answers == {("a", 1): [{"type": "measure", "normalized_title": "Fák", "text": "Fák",
                                   "page": 1, "excerpt": "fák ültetése"}], ("a", 2): []}
