import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "migrate_local", Path(__file__).resolve().parents[2] / "scripts" / "ops" / "migrate_local.py")
migrate_local = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_local)


def _commitment(cid, title="Zöld utcák"):
    return {"id": cid, "candidate_id": 8, "title": title, "kind": "objective", "parent_id": None}


def _data():
    ev = lambda eid, cid, url: {"id": eid, "commitment_id": cid, "url": url, "snippet": "s"}  # noqa: E731
    link = lambda lid, cid, eid, status, rel=None: {  # noqa: E731
        "id": lid, "commitment_id": cid, "evidence_id": eid, "review_status": status,
        "relationship": rel}
    return {
        "commitments": [_commitment(8), _commitment(49, "Zöld utcák "), _commitment(67)],
        "evidence": [ev(1, 8, "a"), ev(2, 49, "a"), ev(3, 49, "b"), ev(4, 8, "b"), ev(5, 67, "c")],
        "links": [
            link(10, 8, 1, "accepted", "supporting"),
            link(11, 49, 2, "accepted", "related_but_indirect"),  # conflict, lower id wins
            link(12, 8, 4, "unreviewed"),
            link(13, 49, 3, "accepted", "supporting"),  # decided beats unreviewed
            link(14, 67, 5, "unreviewed"),
        ],
        "budgets": [
            {"id": 20, "evidence_id": 1, "kind": "estimated_cost", "amount_huf": 5},
            {"id": 21, "evidence_id": 2, "kind": "estimated_cost", "amount_huf": 5},
        ],
    }


def test_merge_keeps_lowest_commitment_and_every_decision():
    data = _data()
    report = migrate_local.merge_duplicate_commitments(data)
    assert [c["id"] for c in data["commitments"]] == [8]
    assert report["commitments_merged"] == {"49": 8, "67": 8}
    links = {(row["evidence_id"], row["review_status"], row["relationship"])
             for row in data["links"]}
    assert links == {(1, "accepted", "supporting"), (4, "accepted", "supporting"),
                     (5, "unreviewed", None)}
    assert all(row["commitment_id"] == 8 for row in data["links"] + data["evidence"])
    assert [b["id"] for b in data["budgets"]] == [20]


def test_merge_refuses_copies_that_really_differ():
    data = _data()
    data["commitments"][1]["kind"] = "target"
    with pytest.raises(ValueError, match="merge by hand"):
        migrate_local.merge_duplicate_commitments(data)
