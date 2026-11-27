from types import SimpleNamespace

from paper_trail.domain.enums import CandidateType, ReviewStatus
from paper_trail.domain.models import Commitment, PolicyCandidate
from paper_trail.services.workspace_service import (
    build_rows,
    display_title,
    matches_filter,
    stage_counts,
)


def cand(id, title="Fák ültetése", kind=CandidateType.MEASURE, status=ReviewStatus.UNREVIEWED,
         page=3, code=None):
    return PolicyCandidate(id=id, document_id=1, suggested_type=kind, text=f"{title} szöveg",
                           normalized_title=title, source_page=page, source_excerpt=title,
                           review_status=status, code=code)


def link(commitment_id, status=ReviewStatus.UNREVIEWED, evidence=True):
    return SimpleNamespace(link=SimpleNamespace(commitment_id=commitment_id, review_status=status),
                           evidence=object() if evidence else None)


def trail_row(commitment_id, n_evidence):
    return SimpleNamespace(commitment=SimpleNamespace(id=commitment_id), evidence=[1] * n_evidence)


def test_same_title_and_kind_is_one_row_with_every_mention():
    rows = build_rows([cand(1), cand(2, "**Fák ültetése.**", page=9), cand(3, "Napelemek")],
                      [], [], [])
    assert [[c.id for c in r.group] for r in rows] == [[1, 2], [3]]


def test_stage_follows_the_pipeline():
    acc, rej = ReviewStatus.ACCEPTED, ReviewStatus.REJECTED
    cands = [cand(1, "a"), cand(2, "b", status=rej), cand(3, "c", status=acc),
             cand(4, "d", status=acc), cand(5, "e", status=acc),
             cand(6, "f", kind=CandidateType.INDICATOR, status=acc)]
    coms = [Commitment(id=10 + i, candidate_id=i, kind=CandidateType.MEASURE, title="x")
            for i in (3, 4, 5, 6)]
    rows = build_rows(cands, coms, [link(13), link(14, ReviewStatus.ACCEPTED)],
                      [trail_row(14, 2)])
    assert {r.title: r.stage for r in rows} == {
        "a": "confirm", "b": "rejected", "c": "review", "d": "done", "e": "search",
        # Indicators aren't searched, so confirmed means done.
        "f": "done"}


def test_filters_hide_rejected_by_default_and_search_text_and_codes():
    rows = build_rows([cand(1, "Fák"), cand(2, "Napelem", status=ReviewStatus.REJECTED),
                       cand(3, "Esővíz", code="M1.2")], [], [], [])
    keep = lambda **kw: [r.title for r in rows if matches_filter(r, **kw)]  # noqa: E731
    assert keep(stage="all", kind="all", q="") == ["Fák", "Esővíz"]
    assert keep(stage="rejected", kind="all", q="") == ["Napelem"]
    assert keep(stage="all", kind="all", q="m1.2") == ["Esővíz"]
    assert keep(stage="all", kind="objective", q="") == []


def test_stage_counts_cover_every_row_whatever_the_filter():
    rows = build_rows([cand(1, "a"), cand(2, "b", status=ReviewStatus.REJECTED)], [], [], [])
    assert stage_counts(rows) == {"confirm": 1, "search": 0, "review": 0, "done": 0, "rejected": 1}


def test_display_title_strips_markdown_and_edge_punctuation():
    assert display_title("  **– Fák ültetése:** ") == "Fák ültetése"
    assert display_title(None) == ""
