"""the sql store: postgres via sqlalchemy core, rows map to domain models in mapping.py"""

from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Connection, Engine

from ..domain.enums import (
    ArtifactStatus,
    CandidateType,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
)
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    ImplementationArtifact,
    Note,
    OfficialSource,
    PolicyCandidate,
    SourceDocument,
)
from .mapping import (
    ARTIFACT_RANK,
    POLARITY_STATUS,
    to_link,
    to_model,
)


@lru_cache(maxsize=8)
def engine(dsn: str) -> Engine:
    """postgres, url or libpq conninfo ("host=.. user=..") alike"""
    import psycopg
    # creator takes both forms, sqlalchemy's own url parser only does urls
    return create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(dsn),
                         pool_pre_ping=True, pool_size=5, max_overflow=5)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class Repo:
    """pooled engine + tiny query helpers, every postgres store builds on this"""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._engine = engine(dsn)

    def _lock(self, conn: Connection, key: str) -> None:
        # racing writers of the same row wait for each other
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": key})

    def _one(self, sql: str, **params):
        with self._engine.begin() as conn:
            return conn.execute(text(sql), params).mappings().first()

    def _all(self, sql: str, **params):
        stmt = text(sql)
        for name, value in params.items():
            if isinstance(value, list):
                stmt = stmt.bindparams(bindparam(name, expanding=True))
        with self._engine.begin() as conn:
            return conn.execute(stmt, params).mappings().all()

    def _exec(self, sql: str, **params) -> int:
        with self._engine.begin() as conn:
            return conn.execute(text(sql), params).rowcount


class PolicyRepository(Repo):
    """documents, candidates, commitments, language profiles"""

    def add_document(self, doc: SourceDocument) -> int:
        p = {"title": doc.title, "publisher": doc.publisher, "url": doc.url}
        with self._engine.begin() as conn:
            conn.execute(text("INSERT INTO documents(title, publisher, url)"
                              " VALUES (:title, :publisher, :url)"
                              " ON CONFLICT(title, publisher, url) DO NOTHING"), p)
            return conn.execute(text("SELECT id FROM documents WHERE title=:title"
                                     " AND publisher=:publisher AND url=:url"), p).scalar_one()

    def documents(self) -> list[SourceDocument]:
        return [SourceDocument(id=r["id"], title=r["title"], publisher=r["publisher"], url=r["url"])
                for r in self._all("SELECT * FROM documents ORDER BY id")]

    def add_candidate(self, cand: PolicyCandidate) -> int:
        with self._engine.begin() as conn:
            # same (doc, page, text) = same candidate, re-ingest keeps its review status
            self._lock(conn, f"candidate:{cand.document_id}:{cand.source_page}:{cand.text}")
            found = conn.execute(text(
                "SELECT id FROM candidates WHERE document_id=:d AND source_page=:p AND text=:t"),
                {"d": cand.document_id, "p": cand.source_page, "t": cand.text}).scalar()
            if found:
                return found
            return conn.execute(text(
                "INSERT INTO candidates(document_id, suggested_type, text, normalized_title,"
                " source_page, source_excerpt, code, excerpt_on_page, responsible_org,"
                " timeframe, deadline_year, unit, target_value)"
                " VALUES (:document_id, :suggested_type, :text, :normalized_title, :source_page,"
                " :source_excerpt, :code, :excerpt_on_page, :responsible_org, :timeframe,"
                " :deadline_year, :unit, :target_value) RETURNING id"),
                {**cand.model_dump(include={
                    "document_id", "text", "normalized_title", "source_page", "source_excerpt",
                    "code", "responsible_org", "timeframe", "deadline_year", "unit",
                    "target_value"}),
                 "suggested_type": cand.suggested_type.value,
                 "excerpt_on_page": None if cand.excerpt_on_page is None
                 else bool(cand.excerpt_on_page)}).scalar_one()

    def candidates(self, status: ReviewStatus | None = None) -> list[PolicyCandidate]:
        where = " WHERE review_status=:s" if status else ""
        rows = self._all(f"SELECT * FROM candidates{where} ORDER BY source_page",
                         s=status and status.value)
        return [to_model(PolicyCandidate, r) for r in rows]

    def candidate(self, candidate_id: int) -> PolicyCandidate | None:
        row = self._one("SELECT * FROM candidates WHERE id=:id", id=candidate_id)
        return to_model(PolicyCandidate, row) if row else None

    def set_candidate_status(self, candidate_id: int, status: ReviewStatus) -> None:
        self._exec("UPDATE candidates SET review_status=:s WHERE id=:id",
                   s=status.value, id=candidate_id)

    def add_commitment(self, com: Commitment) -> int:
        with self._engine.begin() as conn:
            # one commitment per candidate, a double accept gets the same row
            self._lock(conn, f"commitment:{com.candidate_id}")
            if com.candidate_id is not None:
                found = conn.execute(text("SELECT id FROM commitments WHERE candidate_id=:c"),
                                     {"c": com.candidate_id}).scalar()
                if found:
                    return found
            return conn.execute(text(
                "INSERT INTO commitments(candidate_id, parent_id, kind, title, summary, code,"
                " responsible_org, timeframe, deadline_year, unit, target_value, source_page,"
                " asset_owner_jurisdiction) VALUES (:candidate_id, :parent_id, :kind, :title,"
                " :summary, :code, :responsible_org, :timeframe, :deadline_year, :unit,"
                " :target_value, :source_page, :jurisdiction) RETURNING id"),
                {**com.model_dump(include={
                    "candidate_id", "parent_id", "title", "summary", "code", "responsible_org",
                    "timeframe", "deadline_year", "unit", "target_value", "source_page"}),
                 "kind": com.kind.value,
                 "jurisdiction": com.asset_owner_jurisdiction.value}).scalar_one()

    def set_commitment_jurisdiction(self, commitment_id: int,
                                    jurisdiction: Jurisdiction) -> None:
        self._exec("UPDATE commitments SET asset_owner_jurisdiction=:j WHERE id=:id",
                   j=jurisdiction.value, id=commitment_id)

    def language_profile(self, code: str) -> dict | None:
        row = self._one("SELECT profile FROM language_profiles WHERE code=:c", c=code)
        return json.loads(row["profile"]) if row else None

    def put_language_profile(self, code: str, profile: dict) -> None:
        self._exec("INSERT INTO language_profiles(code, profile, updated_at)"
                   " VALUES (:c, :p, CURRENT_TIMESTAMP) ON CONFLICT(code) DO UPDATE"
                   " SET profile=excluded.profile, updated_at=excluded.updated_at",
                   c=code, p=_json(profile))

    def notes(self, kind: str, ids: list[int]) -> dict[int, Note]:
        if not ids:
            return {}
        rows = self._all("SELECT * FROM notes WHERE subject_kind=:k AND subject_id IN :ids",
                         k=kind, ids=ids)
        return {r["subject_id"]: Note.model_validate(dict(r)) for r in rows}

    def put_note(self, note: Note) -> None:
        p = note.model_dump()
        self._exec("INSERT INTO notes(subject_kind, subject_id, title_en, summary_en, suggestion,"
                   " reason_en, author, updated_at) VALUES (:subject_kind, :subject_id,"
                   " :title_en, :summary_en, :suggestion, :reason_en, :author, CURRENT_TIMESTAMP)"
                   " ON CONFLICT(subject_kind, subject_id) DO UPDATE SET"
                   " title_en=excluded.title_en, summary_en=excluded.summary_en,"
                   " suggestion=excluded.suggestion, reason_en=excluded.reason_en,"
                   " author=excluded.author, updated_at=excluded.updated_at", **p)

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]:
        where = " WHERE kind=:k" if kind else ""
        rows = self._all(f"SELECT * FROM commitments{where} ORDER BY code, id",
                         k=kind and kind.value)
        return [to_model(Commitment, r) for r in rows]

    def commitment(self, commitment_id: int) -> Commitment | None:
        row = self._one("SELECT * FROM commitments WHERE id=:id", id=commitment_id)
        return to_model(Commitment, row) if row else None


class EvidenceRepository(Repo):
    """sources, evidence, links, budgets, artifacts, gazetteer"""

    def official_sources(self) -> list[OfficialSource]:
        return [to_model(OfficialSource, r) for r in
                self._all("SELECT * FROM official_sources ORDER BY sort_order, id")]

    def upsert_official_source(self, src: OfficialSource) -> None:
        # a crawler re-finding the page must not wipe its owner
        self._exec("INSERT INTO official_sources(url, title, publisher, sort_order, jurisdiction)"
                   " VALUES (:url, :title, :publisher, :sort_order, :j) ON CONFLICT(url)"
                   " DO UPDATE SET title=excluded.title, publisher=excluded.publisher,"
                   " sort_order=excluded.sort_order,"
                   " jurisdiction=COALESCE(excluded.jurisdiction, official_sources.jurisdiction)",
                   url=src.url, title=src.title, publisher=src.publisher,
                   sort_order=src.sort_order,
                   j=src.jurisdiction.value if src.jurisdiction else None)

    def reviewed_evidence_id(self, commitment_id: int, url: str) -> int | None:
        """evidence a reviewer already decided on, if any"""
        row = self._one("SELECT e.id FROM evidence e JOIN links l ON l.evidence_id = e.id"
                        " WHERE e.commitment_id=:c AND e.url=:u"
                        " AND l.review_status != 'unreviewed' LIMIT 1", c=commitment_id, u=url)
        return row["id"] if row else None

    def add_evidence(self, ev: EvidenceItem) -> int:
        p = {"commitment_id": ev.commitment_id, "url": ev.url, "title": ev.title,
             "publisher": ev.publisher,
             "published_on": ev.published_on.isoformat() if ev.published_on else None,
             "snippet": ev.snippet, "orgs": _json(ev.organisations),
             "locs": _json(ev.locations), "dates": _json(ev.dates_mentioned),
             "hint": ev.status_hint.value, "excerpt": ev.status_excerpt,
             "polarity": ev.polarity.value, "flags": _json(ev.flags),
             "ids": _json(ev.procurement_ids), "parcels": _json(ev.parcels)}
        with self._engine.begin() as conn:
            # a reviewer signed off on the row -> a re-run can't rewrite the quote
            conn.execute(text(
                "INSERT INTO evidence(commitment_id, url, title, publisher, published_on, snippet,"
                " organisations, locations, dates_mentioned, status_hint, status_excerpt,"
                " polarity, flags, procurement_ids, parcels) VALUES (:commitment_id, :url,"
                " :title, :publisher, :published_on, :snippet, :orgs, :locs, :dates, :hint,"
                " :excerpt, :polarity, :flags, :ids, :parcels) ON CONFLICT(commitment_id, url)"
                " DO UPDATE SET snippet=excluded.snippet, organisations=excluded.organisations,"
                " locations=excluded.locations, dates_mentioned=excluded.dates_mentioned,"
                " status_hint=excluded.status_hint,"
                " status_excerpt=excluded.status_excerpt, polarity=excluded.polarity,"
                " flags=excluded.flags, procurement_ids=excluded.procurement_ids,"
                " parcels=excluded.parcels WHERE NOT EXISTS (SELECT 1 FROM links l"
                " WHERE l.evidence_id = evidence.id AND l.review_status != 'unreviewed')"), p)
            return conn.execute(text("SELECT id FROM evidence WHERE commitment_id=:c AND url=:u"),
                                {"c": ev.commitment_id, "u": ev.url}).scalar_one()

    def evidence(self, evidence_id: int) -> EvidenceItem | None:
        row = self._one("SELECT * FROM evidence WHERE id=:id", id=evidence_id)
        return to_model(EvidenceItem, row) if row else None

    def evidence_many(self, ids: list[int]) -> dict[int, EvidenceItem]:
        if not ids:
            return {}
        return {r["id"]: to_model(EvidenceItem, r)
                for r in self._all("SELECT * FROM evidence WHERE id IN :ids", ids=list(ids))}

    def add_link(self, link: EvidenceLink) -> int:
        f = link.features
        with self._engine.begin() as conn:
            # reviewed links keep their decision, only unreviewed ones get rescored
            conn.execute(text(
                "INSERT INTO links(commitment_id, evidence_id, score, similarity,"
                " shared_organisations, shared_locations, shared_dates, suggested_relationship,"
                " reasons) VALUES (:c, :e, :score, :sim, :orgs, :locs, :dates, :rel, :reasons)"
                " ON CONFLICT(commitment_id, evidence_id) DO UPDATE SET score=excluded.score,"
                " similarity=excluded.similarity,"
                " shared_organisations=excluded.shared_organisations,"
                " shared_locations=excluded.shared_locations, shared_dates=excluded.shared_dates,"
                " suggested_relationship=excluded.suggested_relationship,"
                " reasons=excluded.reasons WHERE links.review_status = 'unreviewed'"),
                {"c": link.commitment_id, "e": link.evidence_id, "score": link.score,
                 "sim": f.semantic_similarity, "orgs": _json(f.shared_organisations),
                 "locs": _json(f.shared_locations), "dates": _json(f.shared_dates),
                 "rel": link.suggested_relationship.value, "reasons": _json(link.reasons)})
            return conn.execute(text("SELECT id FROM links WHERE commitment_id=:c"
                                     " AND evidence_id=:e"),
                                {"c": link.commitment_id, "e": link.evidence_id}).scalar_one()

    def links(self, status: ReviewStatus | None = None) -> list[EvidenceLink]:
        where = " WHERE review_status=:s" if status else ""
        rows = self._all(f"SELECT * FROM links{where} ORDER BY score DESC",
                         s=status and status.value)
        return [to_link(r) for r in rows]

    def links_for(self, commitment_id: int) -> list[EvidenceLink]:
        return [to_link(r) for r in self._all(
            "SELECT * FROM links WHERE commitment_id=:c ORDER BY score DESC", c=commitment_id)]

    def link(self, link_id: int) -> EvidenceLink | None:
        row = self._one("SELECT * FROM links WHERE id=:id", id=link_id)
        return to_link(row) if row else None

    def decide_link(self, link_id: int, status: ReviewStatus,
                    relationship: RelationshipType | None = None) -> None:
        self._exec("UPDATE links SET review_status=:s, relationship=:r WHERE id=:id",
                   s=status.value, r=relationship.value if relationship else None, id=link_id)

    def add_budget(self, b: BudgetRecord) -> int:
        p = {"e": b.evidence_id, "kind": b.kind.value, "raw": b.amount_raw, "year": b.fiscal_year,
             "desc": b.description, "cur": b.currency}
        with self._engine.begin() as conn:
            # evidence upserts, so a re-run lands here again: don't store the figure twice
            self._lock(conn, f"budget:{b.evidence_id}")
            found = conn.execute(text(
                "SELECT id FROM budgets WHERE evidence_id=:e AND kind=:kind AND amount_raw=:raw"
                " AND fiscal_year IS NOT DISTINCT FROM :year AND description=:desc"
                " AND currency=:cur"), p).scalar()
            if found:
                return found
            return conn.execute(text(
                "INSERT INTO budgets(evidence_id, kind, amount_huf, amount_raw, fiscal_year,"
                " description, source_url, currency, amount_native) VALUES (:e, :kind, :huf,"
                " :raw, :year, :desc, :url, :cur, :native) RETURNING id"),
                {**p, "huf": b.amount_huf, "url": b.source_url,
                 "native": b.amount_native}).scalar_one()

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]:
        return [to_model(BudgetRecord, r) for r in self._all(
            "SELECT * FROM budgets WHERE evidence_id=:e ORDER BY id", e=evidence_id)]

    def budgets_many(self, evidence_ids: list[int]) -> dict[int, list[BudgetRecord]]:
        out: dict[int, list[BudgetRecord]] = {}
        if evidence_ids:
            for r in self._all("SELECT * FROM budgets WHERE evidence_id IN :ids ORDER BY id",
                               ids=list(evidence_ids)):
                out.setdefault(r["evidence_id"], []).append(to_model(BudgetRecord, r))
        return out

    # artifacts (m:n through evidence) + gazetteer

    def link_artifact(self, procurement_id: str, evidence_id: int,
                      polarity: EvidencePolarity) -> ImplementationArtifact:
        status = POLARITY_STATUS[polarity]
        with self._engine.begin() as conn:
            conn.execute(text("INSERT INTO implementation_artifacts(procurement_id) VALUES (:p)"
                              " ON CONFLICT(procurement_id) DO NOTHING"), {"p": procurement_id})
            row = conn.execute(text("SELECT * FROM implementation_artifacts"
                                    " WHERE procurement_id=:p FOR UPDATE"),
                               {"p": procurement_id}).mappings().one()
            # status only ever escalates: active -> amended -> terminated
            if ARTIFACT_RANK[status] > ARTIFACT_RANK[ArtifactStatus(row["status"])]:
                row = conn.execute(text(
                    "UPDATE implementation_artifacts SET status=:s, status_evidence_id=:e,"
                    " updated_at=CURRENT_TIMESTAMP WHERE id=:id RETURNING *"),
                    {"s": status.value, "e": evidence_id, "id": row["id"]}).mappings().one()
            conn.execute(text("INSERT INTO artifact_evidence(artifact_id, evidence_id)"
                              " VALUES (:a, :e) ON CONFLICT DO NOTHING"),
                         {"a": row["id"], "e": evidence_id})
        return to_model(ImplementationArtifact, row)

    def artifacts_many(self, evidence_ids: list[int]) -> dict[int, list[ImplementationArtifact]]:
        out: dict[int, list[ImplementationArtifact]] = {}
        if evidence_ids:
            for r in self._all("SELECT ae.evidence_id, a.* FROM artifact_evidence ae"
                               " JOIN implementation_artifacts a ON a.id = ae.artifact_id"
                               " WHERE ae.evidence_id IN :ids", ids=list(evidence_ids)):
                out.setdefault(r["evidence_id"], []).append(to_model(ImplementationArtifact, r))
        return out

    def resolve_parcel(self, parcel: str) -> str | None:
        """street a parcel belongs to, confirmed rows first"""
        row = self._one("SELECT canonical_name FROM places WHERE kind='parcel' AND name=:p"
                        " ORDER BY confirmed DESC, id LIMIT 1", p=parcel)
        return row["canonical_name"] if row else None

    def record_parcel(self, parcel: str, street: str, source: str) -> None:
        """unconfirmed until a person checks it, the first street seen sticks"""
        self._exec("INSERT INTO places(kind, name, canonical_name, source)"
                   " VALUES ('parcel', :p, :s, :src) ON CONFLICT DO NOTHING",
                   p=parcel, s=street, src=source)

    def upsert_place(self, kind: str, name: str, canonical_name: str, district: str,
                     osm_id: str | None, geojson: str | None, source: str) -> None:
        self._exec("INSERT INTO places(kind, name, canonical_name, district, osm_id, geojson,"
                   " source, confirmed) VALUES (:k, :n, :c, :d, :o, :g, :s, TRUE)"
                   " ON CONFLICT(kind, name, district) DO UPDATE SET osm_id=excluded.osm_id,"
                   " geojson=excluded.geojson",
                   k=kind, n=name, c=canonical_name, d=district, o=osm_id, g=geojson, s=source)

    def place_names(self) -> list[str]:
        return [r["name"] for r in
                self._all("SELECT DISTINCT name FROM places WHERE kind != 'parcel'")]
