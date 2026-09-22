"""Regression: repositories hold the DB path, not a connection — a repo
created on one thread must be usable from any other thread (Streamlit
runs each interaction on a different execution thread)."""

import threading

from paper_trail.domain.enums import CandidateType, ReviewStatus
from paper_trail.domain.models import PolicyCandidate, SourceDocument
from paper_trail.repositories.store import EvidenceRepository, PolicyRepository


def _seed(policy: PolicyRepository) -> int:
    doc_id = policy.add_document(
        SourceDocument(title="Strategy", publisher="JK"))
    cand = PolicyCandidate(
        document_id=doc_id, suggested_type=CandidateType.MEASURE,
        text="Utcai fák ültetése", normalized_title="Utcafásítás",
        source_page=1, source_excerpt="Utcai fák ültetése", code="A1")
    return policy.add_candidate(cand)


def test_repo_created_on_one_thread_used_on_another(db_path):
    policy = PolicyRepository(db_path)          # created on this thread
    evidence = EvidenceRepository(db_path)
    cand_id = _seed(policy)

    errors = []

    def work():
        try:
            cands = policy.candidates(status=ReviewStatus.UNREVIEWED)
            assert [c.id for c in cands] == [cand_id]
            assert policy.documents()[0].title == "Strategy"
            assert evidence.links() == []
        except Exception as e:                  # sqlite3.ProgrammingError
            errors.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert not errors, errors


def test_write_from_other_thread_commits(db_path):
    policy = PolicyRepository(db_path)
    errors = []

    def work():
        try:
            _seed(policy)
            policy.set_candidate_status(1, ReviewStatus.ACCEPTED)
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert not errors, errors

    # the write must be committed and visible from a fresh connection
    cands = policy.candidates(status=ReviewStatus.ACCEPTED)
    assert len(cands) == 1
    assert cands[0].review_status == ReviewStatus.ACCEPTED
