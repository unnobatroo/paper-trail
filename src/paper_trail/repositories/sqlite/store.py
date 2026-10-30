from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from ...domain.enums import (
    ArtifactStatus,
    CandidateType,
    EvidencePolarity,
    Jurisdiction,
    RelationshipType,
    ReviewStatus,
)
from ...domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    ImplementationArtifact,
    OfficialSource,
    PolicyCandidate,
    SourceDocument,
)
from ..mapping import (
    ARTIFACT_RANK,
    POLARITY_STATUS,
    to_artifact,
    to_budget,
    to_candidate,
    to_commitment,
    to_evidence,
    to_link,
    to_official_source,
)
from .schema import connect, init_db


class _Repo:
    """db path + one short-lived connection per call"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        init_db(self.db_path)

    @contextmanager
    def _connect(self):
        """commit on success, roll back on error, always close"""
        conn = connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()


class PolicyRepository(_Repo):
    """documents, candidates, commitments"""

    def add_document(self, doc: SourceDocument) -> int:
        # natural-key dedupe, a retried ingest gets the same row
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents(title, publisher, url) VALUES (?,?,?)"
                " ON CONFLICT(title, publisher, url) DO NOTHING",
                (doc.title, doc.publisher, doc.url),
            )
            return conn.execute(
                "SELECT id FROM documents"
                " WHERE title=? AND publisher=? AND url=?",
                (doc.title, doc.publisher, doc.url)).fetchone()["id"]

    def documents(self) -> list[SourceDocument]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY id").fetchall()
        return [
            SourceDocument(id=r["id"], title=r["title"], publisher=r["publisher"],
                           url=r["url"])
            for r in rows
        ]

    def add_candidate(self, cand: PolicyCandidate) -> int:
        # dedupe on (doc, page, text), re-ingest keeps rows + their review status
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM candidates WHERE document_id=?"
                " AND source_page=? AND text=?",
                (cand.document_id, cand.source_page, cand.text)).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                """INSERT INTO candidates(document_id, suggested_type, text, normalized_title,
                                          source_page, source_excerpt, code, excerpt_on_page,
                                          responsible_org,
                                          timeframe, deadline_year, unit, target_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cand.document_id, cand.suggested_type.value, cand.text, cand.normalized_title,
                 cand.source_page, cand.source_excerpt, cand.code,
                 None if cand.excerpt_on_page is None else int(cand.excerpt_on_page),
                 cand.responsible_org, cand.timeframe, cand.deadline_year,
                 cand.unit, cand.target_value),
            )
            return cur.lastrowid

    def candidates(self, status: ReviewStatus | None = None) -> list[PolicyCandidate]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM candidates WHERE review_status=? ORDER BY source_page",
                    (status.value,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM candidates ORDER BY source_page").fetchall()
        return [to_candidate(r) for r in rows]

    def candidate(self, candidate_id: int) -> PolicyCandidate | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id=?",
                               (candidate_id,)).fetchone()
        return to_candidate(row) if row else None

    def set_candidate_status(self, candidate_id: int, status: ReviewStatus) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET review_status=? WHERE id=?",
                         (status.value, candidate_id))

    def add_commitment(self, com: Commitment) -> int:
        with self._connect() as conn:
            # one commitment per candidate, double accept gets the same row
            if com.candidate_id is not None:
                row = conn.execute(
                    "SELECT id FROM commitments WHERE candidate_id=?",
                    (com.candidate_id,)).fetchone()
                if row:
                    return row["id"]
            cur = conn.execute(
                """INSERT INTO commitments(candidate_id, parent_id, kind, title, summary, code,
                                           responsible_org, timeframe, deadline_year,
                                           unit, target_value, source_page,
                                           asset_owner_jurisdiction)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (com.candidate_id, com.parent_id, com.kind.value, com.title, com.summary,
                 com.code, com.responsible_org, com.timeframe, com.deadline_year,
                 com.unit, com.target_value, com.source_page,
                 com.asset_owner_jurisdiction.value),
            )
            return cur.lastrowid

    def set_commitment_jurisdiction(self, commitment_id: int,
                                    jurisdiction: Jurisdiction) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE commitments SET asset_owner_jurisdiction=? WHERE id=?",
                         (jurisdiction.value, commitment_id))

    def language_profile(self, code: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT profile FROM language_profiles WHERE code=?",
                               (code,)).fetchone()
        return json.loads(row["profile"]) if row else None

    def put_language_profile(self, code: str, profile: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO language_profiles(code, profile, updated_at)"
                " VALUES (?, ?, datetime('now'))"
                " ON CONFLICT(code) DO UPDATE SET profile=excluded.profile,"
                " updated_at=excluded.updated_at",
                (code, json.dumps(profile, ensure_ascii=False)))

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]:
        with self._connect() as conn:
            if kind:
                rows = conn.execute(
                    "SELECT * FROM commitments WHERE kind=? ORDER BY code, id",
                    (kind.value,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM commitments ORDER BY code, id").fetchall()
        return [to_commitment(r) for r in rows]

    def commitment(self, commitment_id: int) -> Commitment | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM commitments WHERE id=?",
                               (commitment_id,)).fetchone()
        return to_commitment(row) if row else None


class EvidenceRepository(_Repo):
    """evidence, links, budgets"""

    # official_sources: what the evidence search always checks
    def official_sources(self) -> list[OfficialSource]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM official_sources ORDER BY sort_order, id"
            ).fetchall()
        return [to_official_source(r) for r in rows]

    def upsert_official_source(self, src: OfficialSource) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO official_sources(url, title, publisher, sort_order, jurisdiction)"
                " VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET"
                " title=excluded.title, publisher=excluded.publisher,"
                " sort_order=excluded.sort_order,"
                # a crawler re-finding the page must not wipe its owner
                " jurisdiction=COALESCE(excluded.jurisdiction, official_sources.jurisdiction)",
                (src.url, src.title, src.publisher, src.sort_order,
                 src.jurisdiction.value if src.jurisdiction else None),
            )

    def reviewed_evidence_id(self, commitment_id: int, url: str) -> int | None:
        """evidence id a reviewer already decided on, if any"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT e.id
                   FROM evidence e
                            JOIN links l ON l.evidence_id = e.id
                   WHERE e.commitment_id = ?
                     AND e.url = ?
                     AND l.review_status != 'unreviewed'
                   LIMIT 1""", (commitment_id, url)).fetchone()
        return row["id"] if row else None

    def add_evidence(self, ev: EvidenceItem) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO evidence(commitment_id, url, title, publisher, published_on,
                                        snippet, organisations, locations, dates_mentioned,
                                        status_hint, status_excerpt, polarity, flags,
                                        procurement_ids, parcels)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(commitment_id, url) DO
                UPDATE SET
                    snippet=excluded.snippet, status_hint=excluded.status_hint,
                    status_excerpt=excluded.status_excerpt, polarity=excluded.polarity,
                    flags=excluded.flags, procurement_ids=excluded.procurement_ids,
                    parcels=excluded.parcels
                -- reviewer signed off on this row, a re-run can't rewrite the quote
                WHERE NOT EXISTS (
                    SELECT 1 FROM links l WHERE l.evidence_id = evidence.id
                  AND l.review_status != 'unreviewed')""",
                (ev.commitment_id, ev.url, ev.title, ev.publisher,
                 ev.published_on.isoformat() if ev.published_on else None,
                 ev.snippet,
                 json.dumps(ev.organisations, ensure_ascii=False),
                 json.dumps(ev.locations, ensure_ascii=False),
                 json.dumps(ev.dates_mentioned, ensure_ascii=False),
                 ev.status_hint.value, ev.status_excerpt, ev.polarity.value,
                 json.dumps(ev.flags), json.dumps(ev.procurement_ids),
                 json.dumps(ev.parcels)),
            )
            row = conn.execute(
                "SELECT id FROM evidence WHERE commitment_id=? AND url=?",
                (ev.commitment_id, ev.url)).fetchone()
            return row["id"]

    def evidence(self, evidence_id: int) -> EvidenceItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE id=?",
                               (evidence_id,)).fetchone()
        return to_evidence(row) if row else None

    def evidence_many(self, ids: list[int]) -> dict[int, EvidenceItem]:
        """one query, not one per link"""
        if not ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM evidence WHERE id IN ({','.join('?' * len(ids))})",
                ids).fetchall()
        return {r["id"]: to_evidence(r) for r in rows}

    def add_link(self, link: EvidenceLink) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO links(commitment_id, evidence_id, score, similarity,
                                     shared_organisations, shared_locations, shared_dates,
                                     suggested_relationship, reasons)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(commitment_id, evidence_id) DO
                UPDATE SET
                    score=excluded.score, suggested_relationship=excluded.suggested_relationship,
                    reasons=excluded.reasons
                WHERE links.review_status = 'unreviewed'""",
                (link.commitment_id, link.evidence_id, link.score,
                 link.features.semantic_similarity,
                 json.dumps(link.features.shared_organisations, ensure_ascii=False),
                 json.dumps(link.features.shared_locations, ensure_ascii=False),
                 json.dumps(link.features.shared_dates, ensure_ascii=False),
                 link.suggested_relationship.value,
                 json.dumps(link.reasons, ensure_ascii=False)),
            )
            row = conn.execute(
                "SELECT id FROM links WHERE commitment_id=? AND evidence_id=?",
                (link.commitment_id, link.evidence_id)).fetchone()
            return row["id"]

    def links(self, status: ReviewStatus | None = None) -> list[EvidenceLink]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM links WHERE review_status=? ORDER BY score DESC",
                    (status.value,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM links ORDER BY score DESC").fetchall()
        return [to_link(r) for r in rows]

    def links_for(self, commitment_id: int) -> list[EvidenceLink]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM links WHERE commitment_id=? ORDER BY score DESC",
                (commitment_id,)).fetchall()
        return [to_link(r) for r in rows]

    def link(self, link_id: int) -> EvidenceLink | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM links WHERE id=?",
                               (link_id,)).fetchone()
        return to_link(row) if row else None

    def decide_link(self, link_id: int, status: ReviewStatus,
                    relationship: RelationshipType | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE links SET review_status=?, relationship=? WHERE id=?",
                (status.value,
                 relationship.value if relationship else None, link_id))

    def add_budget(self, b: BudgetRecord) -> int:
        with self._connect() as conn:
            # evidence upserts, so a re-run lands here with the same id,
            # don't insert the figure twice
            row = conn.execute(
                "SELECT id FROM budgets WHERE evidence_id=? AND kind=?"
                " AND amount_raw=? AND fiscal_year IS ? AND description=? AND currency=?",
                (b.evidence_id, b.kind.value, b.amount_raw,
                 b.fiscal_year, b.description, b.currency)).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                """INSERT INTO budgets(evidence_id, kind, amount_huf, amount_raw,
                                       fiscal_year, description, source_url,
                                       currency, amount_native)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (b.evidence_id, b.kind.value, b.amount_huf, b.amount_raw,
                 b.fiscal_year, b.description, b.source_url, b.currency, b.amount_native),
            )
            return cur.lastrowid

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM budgets WHERE evidence_id=? ORDER BY id",
                (evidence_id,)).fetchall()
        return [to_budget(r) for r in rows]

    def budgets_many(
            self, evidence_ids: list[int]) -> dict[int, list[BudgetRecord]]:
        """one query, not one per evidence row"""
        if not evidence_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM budgets WHERE evidence_id IN"
                f" ({','.join('?' * len(evidence_ids))}) ORDER BY id",
                evidence_ids).fetchall()
        out: dict[int, list[BudgetRecord]] = {}
        for r in rows:
            out.setdefault(r["evidence_id"], []).append(to_budget(r))
        return out

    # artifacts (m:n through evidence) + gazetteer

    def link_artifact(self, procurement_id: str, evidence_id: int,
                      polarity: EvidencePolarity) -> ImplementationArtifact:
        status = POLARITY_STATUS[polarity]
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO implementation_artifacts(procurement_id)"
                         " VALUES (?)", (procurement_id,))
            row = conn.execute("SELECT * FROM implementation_artifacts WHERE procurement_id=?",
                               (procurement_id,)).fetchone()
            if ARTIFACT_RANK[status] > ARTIFACT_RANK[ArtifactStatus(row["status"])]:
                conn.execute("UPDATE implementation_artifacts SET status=?,"
                             " status_evidence_id=?, updated_at=datetime('now') WHERE id=?",
                             (status.value, evidence_id, row["id"]))
            conn.execute("INSERT OR IGNORE INTO artifact_evidence(artifact_id, evidence_id)"
                         " VALUES (?, ?)", (row["id"], evidence_id))
            row = conn.execute("SELECT * FROM implementation_artifacts WHERE id=?",
                               (row["id"],)).fetchone()
        return to_artifact(row)

    def artifacts_many(self, evidence_ids: list[int]
                       ) -> dict[int, list[ImplementationArtifact]]:
        if not evidence_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ae.evidence_id, a.* FROM artifact_evidence ae JOIN"
                " implementation_artifacts a ON a.id = ae.artifact_id WHERE ae.evidence_id IN"
                f" ({','.join('?' * len(evidence_ids))})", evidence_ids).fetchall()
        out: dict[int, list[ImplementationArtifact]] = {}
        for r in rows:
            out.setdefault(r["evidence_id"], []).append(to_artifact(r))
        return out

    def resolve_parcel(self, parcel: str) -> str | None:
        """street a parcel belongs to, confirmed entries first"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT canonical_name FROM places WHERE kind='parcel' AND name=?"
                " ORDER BY confirmed DESC, id LIMIT 1", (parcel,)).fetchone()
        return row["canonical_name"] if row else None

    def record_parcel(self, parcel: str, street: str, source: str) -> None:
        """unconfirmed until a person checks, first street seen sticks"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO places(kind, name, canonical_name, source)"
                " VALUES ('parcel', ?, ?, ?)", (parcel, street, source))

    def upsert_place(self, kind: str, name: str, canonical_name: str, district: str,
                     osm_id: str | None, geojson: str | None, source: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO places(kind, name, canonical_name, district, osm_id, geojson,
                                      source, confirmed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(kind, name, district) DO UPDATE SET
                       osm_id=excluded.osm_id, geojson=excluded.geojson""",
                (kind, name, canonical_name, district, osm_id, geojson, source))

    def place_names(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT name FROM places WHERE kind != 'parcel'"
                                ).fetchall()
        return [r["name"] for r in rows]
