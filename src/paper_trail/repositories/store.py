"""Data access. Two small repositories; the only layer that speaks SQL.

Repositories hold the database *path*, never a connection — a sqlite3
connection is bound to the thread that created it and Streamlit runs each
interaction on a different thread. Every operation opens, uses and closes
its own connection via `_connect()`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping

from ..domain.enums import (
    BudgetKind,
    CandidateType,
    RelationshipType,
    ReviewStatus,
    Status,
)
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    MatchFeatures,
    PolicyCandidate,
    SourceDocument,
)
from ..infrastructure.database import connect, init_db


class _Repo:
    """Shared base: database path + one short-lived connection per call."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        init_db(self.db_path)

    @contextmanager
    def _connect(self):
        """Yield a connection; commit on success, roll back on error,
        always close. Keeps no state between calls."""
        conn = connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def _date(value: str | None):
    from datetime import date

    return date.fromisoformat(value) if value else None


def _candidate(row: Mapping) -> PolicyCandidate:
    return PolicyCandidate(
        id=row["id"],
        document_id=row["document_id"],
        suggested_type=CandidateType(row["suggested_type"]),
        text=row["text"],
        normalized_title=row["normalized_title"],
        source_page=row["source_page"],
        source_excerpt=row["source_excerpt"],
        code=row["code"],
        excerpt_on_page=bool(row["excerpt_on_page"]) if row["excerpt_on_page"] is not None else None,
        responsible_org=row["responsible_org"],
        timeframe=row["timeframe"],
        deadline_year=row["deadline_year"],
        unit=row["unit"],
        target_value=row["target_value"],
        review_status=ReviewStatus(row["review_status"]),
    )


def _commitment(row: Mapping) -> Commitment:
    return Commitment(
        id=row["id"],
        candidate_id=row["candidate_id"],
        parent_id=row["parent_id"],
        kind=CandidateType(row["kind"]),
        title=row["title"],
        summary=row["summary"],
        code=row["code"],
        responsible_org=row["responsible_org"],
        timeframe=row["timeframe"],
        deadline_year=row["deadline_year"],
        unit=row["unit"],
        target_value=row["target_value"],
        source_page=row["source_page"],
    )


def _evidence(row: Mapping) -> EvidenceItem:
    return EvidenceItem(
        id=row["id"],
        commitment_id=row["commitment_id"],
        url=row["url"],
        title=row["title"],
        publisher=row["publisher"],
        published_on=_date(row["published_on"]),
        snippet=row["snippet"],
        organisations=json.loads(row["organisations"]),
        locations=json.loads(row["locations"]),
        dates_mentioned=json.loads(row["dates_mentioned"]),
        status_hint=Status(row["status_hint"]),
        status_excerpt=row["status_excerpt"],
    )


def _link(row: Mapping) -> EvidenceLink:
    return EvidenceLink(
        id=row["id"],
        commitment_id=row["commitment_id"],
        evidence_id=row["evidence_id"],
        score=row["score"],
        suggested_relationship=RelationshipType(row["suggested_relationship"]),
        reasons=json.loads(row["reasons"]),
        relationship=RelationshipType(row["relationship"]) if row["relationship"] else None,
        review_status=ReviewStatus(row["review_status"]),
        features=MatchFeatures(
            semantic_similarity=row["similarity"],
            shared_organisations=json.loads(row["shared_organisations"]),
            shared_locations=json.loads(row["shared_locations"]),
            shared_dates=json.loads(row["shared_dates"]),
        ),
    )


def _budget(row: Mapping) -> BudgetRecord:
    return BudgetRecord(
        id=row["id"],
        evidence_id=row["evidence_id"],
        kind=BudgetKind(row["kind"]),
        amount_huf=row["amount_huf"],
        amount_raw=row["amount_raw"],
        fiscal_year=row["fiscal_year"],
        description=row["description"],
        source_url=row["source_url"],
    )


class PolicyRepository(_Repo):
    """Documents, extraction candidates and accepted commitments."""

    # documents -----------------------------------------------------------
    def add_document(self, doc: SourceDocument) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO documents(title, publisher, url) VALUES (?,?,?)",
                (doc.title, doc.publisher, doc.url),
            )
            return cur.lastrowid

    def documents(self) -> list[SourceDocument]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY id").fetchall()
        return [
            SourceDocument(id=r["id"], title=r["title"], publisher=r["publisher"],
                           url=r["url"])
            for r in rows
        ]

    # candidates ----------------------------------------------------------
    def add_candidate(self, cand: PolicyCandidate) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO candidates(document_id, suggested_type, text, normalized_title,
                   source_page, source_excerpt, code, excerpt_on_page, responsible_org,
                   timeframe, deadline_year, unit, target_value)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
        return [_candidate(r) for r in rows]

    def candidate(self, candidate_id: int) -> PolicyCandidate | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id=?",
                               (candidate_id,)).fetchone()
        return _candidate(row) if row else None

    def set_candidate_status(self, candidate_id: int, status: ReviewStatus) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET review_status=? WHERE id=?",
                         (status.value, candidate_id))

    # commitments ---------------------------------------------------------
    def add_commitment(self, com: Commitment) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO commitments(candidate_id, parent_id, kind, title, summary, code,
                   responsible_org, timeframe, deadline_year, unit, target_value, source_page)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (com.candidate_id, com.parent_id, com.kind.value, com.title, com.summary,
                 com.code, com.responsible_org, com.timeframe, com.deadline_year,
                 com.unit, com.target_value, com.source_page),
            )
            return cur.lastrowid

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]:
        with self._connect() as conn:
            if kind:
                rows = conn.execute(
                    "SELECT * FROM commitments WHERE kind=? ORDER BY code, id",
                    (kind.value,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM commitments ORDER BY code, id").fetchall()
        return [_commitment(r) for r in rows]

    def commitment(self, commitment_id: int) -> Commitment | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM commitments WHERE id=?",
                               (commitment_id,)).fetchone()
        return _commitment(row) if row else None


class EvidenceRepository(_Repo):
    """Retrieved evidence, proposed links and extracted budget figures."""

    def add_evidence(self, ev: EvidenceItem) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO evidence(commitment_id, url, title, publisher, published_on,
                   snippet, organisations, locations, dates_mentioned,
                   status_hint, status_excerpt)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(commitment_id, url) DO UPDATE SET
                     snippet=excluded.snippet, status_hint=excluded.status_hint,
                     status_excerpt=excluded.status_excerpt""",
                (ev.commitment_id, ev.url, ev.title, ev.publisher,
                 ev.published_on.isoformat() if ev.published_on else None,
                 ev.snippet,
                 json.dumps(ev.organisations, ensure_ascii=False),
                 json.dumps(ev.locations, ensure_ascii=False),
                 json.dumps(ev.dates_mentioned, ensure_ascii=False),
                 ev.status_hint.value, ev.status_excerpt),
            )
            row = conn.execute(
                "SELECT id FROM evidence WHERE commitment_id=? AND url=?",
                (ev.commitment_id, ev.url)).fetchone()
            return row["id"]

    def evidence(self, evidence_id: int) -> EvidenceItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE id=?",
                               (evidence_id,)).fetchone()
        return _evidence(row) if row else None

    def add_link(self, link: EvidenceLink) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO links(commitment_id, evidence_id, score, similarity,
                   shared_organisations, shared_locations, shared_dates,
                   suggested_relationship, reasons)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(commitment_id, evidence_id) DO UPDATE SET
                     score=excluded.score, suggested_relationship=excluded.suggested_relationship,
                     reasons=excluded.reasons""",
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
        return [_link(r) for r in rows]

    def links_for(self, commitment_id: int) -> list[EvidenceLink]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM links WHERE commitment_id=? ORDER BY score DESC",
                (commitment_id,)).fetchall()
        return [_link(r) for r in rows]

    def link(self, link_id: int) -> EvidenceLink | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM links WHERE id=?",
                               (link_id,)).fetchone()
        return _link(row) if row else None

    def decide_link(self, link_id: int, status: ReviewStatus,
                    relationship: RelationshipType | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE links SET review_status=?, relationship=? WHERE id=?",
                (status.value,
                 relationship.value if relationship else None, link_id))

    # budgets --------------------------------------------------------------
    def add_budget(self, b: BudgetRecord) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO budgets(evidence_id, kind, amount_huf, amount_raw,
                   fiscal_year, description, source_url) VALUES (?,?,?,?,?,?,?)""",
                (b.evidence_id, b.kind.value, b.amount_huf, b.amount_raw,
                 b.fiscal_year, b.description, b.source_url),
            )
            return cur.lastrowid

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM budgets WHERE evidence_id=? ORDER BY id",
                (evidence_id,)).fetchall()
        return [_budget(r) for r in rows]

