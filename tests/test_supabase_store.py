"""Supabase evidence writes before and after migration 008."""

from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from paper_trail.domain.models import EvidenceItem
from paper_trail.repositories.supabase_store import SupabaseEvidenceRepository


class _Chain:
    """Just enough of the postgrest builder for add_evidence's fallback path."""

    def __init__(self, db, table):
        self.db, self.table = db, table

    def upsert(self, row, on_conflict):
        self.db.upserts.append((self.table, row))
        return self

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def neq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        if self.db.upserts and self.db.upserts[-1][0] == self.table:
            return SimpleNamespace(data=[{"id": 7}])
        return SimpleNamespace(data=[])  # no existing / reviewed rows


class _DB:
    def __init__(self, rpc_error=None):
        self.rpc_error, self.rpc_calls, self.upserts = rpc_error, [], []

    def rpc(self, fn, params):
        self.rpc_calls.append(fn)
        if self.rpc_error:
            raise self.rpc_error
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=42))

    def table(self, name):
        return _Chain(self, name)


EV = EvidenceItem(commitment_id=1, url="https://jozsefvaros.hu/x", title="t")


def test_uses_the_atomic_function_when_migrated():
    db = _DB()
    assert SupabaseEvidenceRepository("u", "k", client=db).add_evidence(EV) == 42
    assert db.rpc_calls == ["upsert_evidence_unless_reviewed"] and not db.upserts


def test_falls_back_before_migration_008_and_stops_asking():
    db = _DB(APIError({"code": "PGRST202", "message": "Could not find the function"}))
    repo = SupabaseEvidenceRepository("u", "k", client=db)
    assert repo.add_evidence(EV) == 7
    assert repo.add_evidence(EV) == 7
    assert db.rpc_calls == ["upsert_evidence_unless_reviewed"]  # asked once, then remembered
    assert [t for t, _ in db.upserts] == ["evidence", "evidence"]


def test_other_rpc_errors_still_surface():
    db = _DB(APIError({"code": "42501", "message": "permission denied"}))
    with pytest.raises(APIError):
        SupabaseEvidenceRepository("u", "k", client=db).add_evidence(EV)
