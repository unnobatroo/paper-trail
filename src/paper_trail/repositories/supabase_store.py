"""Supabase data access — same repository interface, PostgREST over HTTPS.

The supabase-py client is stateless HTTP: there is no connection object to
pin to a thread, so these repositories are safe inside Streamlit's cached
app state by construction. The schema lives in
`supabase/migrations/001_schema.sql` — JSON list columns are stored as TEXT
exactly like the SQLite backend, so the shared row mappers work unchanged.
"""

from __future__ import annotations

import json

from supabase import Client, create_client

from ..domain.enums import CandidateType, RelationshipType, ReviewStatus
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    PolicyCandidate,
    SourceDocument,
)
from .store import _budget, _candidate, _commitment, _evidence, _link


class _SupabaseRepo:
    """Shared base: a Supabase client (stateless HTTP, thread-safe)."""

    def __init__(self, url: str, key: str, client: Client | None = None):
        self._db = client or create_client(url, key)


class SupabasePolicyRepository(_SupabaseRepo):
    """Documents, extraction candidates and accepted commitments."""

    # documents -----------------------------------------------------------
    def add_document(self, doc: SourceDocument) -> int:
        res = self._db.table("documents").insert(
            {"title": doc.title, "publisher": doc.publisher, "url": doc.url}
        ).execute()
        return res.data[0]["id"]

    def documents(self) -> list[SourceDocument]:
        res = self._db.table("documents").select("*").order("id").execute()
        return [
            SourceDocument(id=r["id"], title=r["title"],
                           publisher=r["publisher"], url=r["url"])
            for r in res.data
        ]

    # candidates ----------------------------------------------------------
    def add_candidate(self, cand: PolicyCandidate) -> int:
        res = self._db.table("candidates").insert({
            "document_id": cand.document_id,
            "suggested_type": cand.suggested_type.value,
            "text": cand.text,
            "normalized_title": cand.normalized_title,
            "source_page": cand.source_page,
            "source_excerpt": cand.source_excerpt,
            "code": cand.code,
            "excerpt_on_page": cand.excerpt_on_page,
            "responsible_org": cand.responsible_org,
            "timeframe": cand.timeframe,
            "deadline_year": cand.deadline_year,
            "unit": cand.unit,
            "target_value": cand.target_value,
        }).execute()
        return res.data[0]["id"]

    def candidates(self, status: ReviewStatus | None = None) -> list[PolicyCandidate]:
        q = self._db.table("candidates").select("*")
        if status:
            q = q.eq("review_status", status.value)
        res = q.order("source_page").execute()
        return [_candidate(r) for r in res.data]

    def candidate(self, candidate_id: int) -> PolicyCandidate | None:
        res = (self._db.table("candidates").select("*")
               .eq("id", candidate_id).execute())
        return _candidate(res.data[0]) if res.data else None

    def set_candidate_status(self, candidate_id: int,
                             status: ReviewStatus) -> None:
        (self._db.table("candidates")
         .update({"review_status": status.value})
         .eq("id", candidate_id).execute())

    # commitments ---------------------------------------------------------
    def add_commitment(self, com: Commitment) -> int:
        res = self._db.table("commitments").insert({
            "candidate_id": com.candidate_id,
            "parent_id": com.parent_id,
            "kind": com.kind.value,
            "title": com.title,
            "summary": com.summary,
            "code": com.code,
            "responsible_org": com.responsible_org,
            "timeframe": com.timeframe,
            "deadline_year": com.deadline_year,
            "unit": com.unit,
            "target_value": com.target_value,
            "source_page": com.source_page,
        }).execute()
        return res.data[0]["id"]

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]:
        q = self._db.table("commitments").select("*")
        if kind:
            q = q.eq("kind", kind.value)
        res = q.order("code").order("id").execute()
        return [_commitment(r) for r in res.data]

    def commitment(self, commitment_id: int) -> Commitment | None:
        res = (self._db.table("commitments").select("*")
               .eq("id", commitment_id).execute())
        return _commitment(res.data[0]) if res.data else None


class SupabaseEvidenceRepository(_SupabaseRepo):
    """Retrieved evidence, proposed links and extracted budget figures."""

    def add_evidence(self, ev: EvidenceItem) -> int:
        res = self._db.table("evidence").upsert({
            "commitment_id": ev.commitment_id,
            "url": ev.url,
            "title": ev.title,
            "publisher": ev.publisher,
            "published_on": (ev.published_on.isoformat()
                             if ev.published_on else None),
            "snippet": ev.snippet,
            "organisations": json.dumps(ev.organisations, ensure_ascii=False),
            "locations": json.dumps(ev.locations, ensure_ascii=False),
            "dates_mentioned": json.dumps(ev.dates_mentioned, ensure_ascii=False),
            "status_hint": ev.status_hint.value,
            "status_excerpt": ev.status_excerpt,
        }, on_conflict="commitment_id,url").execute()
        return res.data[0]["id"]

    def evidence(self, evidence_id: int) -> EvidenceItem | None:
        res = (self._db.table("evidence").select("*")
               .eq("id", evidence_id).execute())
        return _evidence(res.data[0]) if res.data else None

    def add_link(self, link: EvidenceLink) -> int:
        res = self._db.table("links").upsert({
            "commitment_id": link.commitment_id,
            "evidence_id": link.evidence_id,
            "score": link.score,
            "similarity": link.features.semantic_similarity,
            "shared_organisations": json.dumps(
                link.features.shared_organisations, ensure_ascii=False),
            "shared_locations": json.dumps(
                link.features.shared_locations, ensure_ascii=False),
            "shared_dates": json.dumps(
                link.features.shared_dates, ensure_ascii=False),
            "suggested_relationship": link.suggested_relationship.value,
            "reasons": json.dumps(link.reasons, ensure_ascii=False),
        }, on_conflict="commitment_id,evidence_id").execute()
        return res.data[0]["id"]

    def links(self, status: ReviewStatus | None = None) -> list[EvidenceLink]:
        q = self._db.table("links").select("*")
        if status:
            q = q.eq("review_status", status.value)
        res = q.order("score", desc=True).execute()
        return [_link(r) for r in res.data]

    def links_for(self, commitment_id: int) -> list[EvidenceLink]:
        res = (self._db.table("links").select("*")
               .eq("commitment_id", commitment_id)
               .order("score", desc=True).execute())
        return [_link(r) for r in res.data]

    def link(self, link_id: int) -> EvidenceLink | None:
        res = (self._db.table("links").select("*")
               .eq("id", link_id).execute())
        return _link(res.data[0]) if res.data else None

    def decide_link(self, link_id: int, status: ReviewStatus,
                    relationship: RelationshipType | None = None) -> None:
        (self._db.table("links")
         .update({"review_status": status.value,
                  "relationship": relationship.value if relationship else None})
         .eq("id", link_id).execute())

    # budgets --------------------------------------------------------------
    def add_budget(self, b: BudgetRecord) -> int:
        res = self._db.table("budgets").insert({
            "evidence_id": b.evidence_id,
            "kind": b.kind.value,
            "amount_huf": b.amount_huf,
            "amount_raw": b.amount_raw,
            "fiscal_year": b.fiscal_year,
            "description": b.description,
            "source_url": b.source_url,
        }).execute()
        return res.data[0]["id"]

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]:
        res = (self._db.table("budgets").select("*")
               .eq("evidence_id", evidence_id).order("id").execute())
        return [_budget(r) for r in res.data]
