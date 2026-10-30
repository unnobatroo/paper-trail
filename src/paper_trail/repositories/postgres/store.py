"""postgres storage, short transactions, rows mapped in ../mapping.py"""

import json
from contextlib import contextmanager

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


def connect(database_url):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10)


class _Repo:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def _connect(self):
        with connect(self.database_url) as conn:
            yield conn


class PostgresPolicyRepository(_Repo):
    """documents, candidates, commitments"""

    def add_document(self, doc: SourceDocument) -> int:
        with self._connect() as conn:
            conn.execute(
                (
                    """INSERT INTO documents(title, publisher, url) VALUES (%s,%s,%s) ON
                    CONFLICT(title, publisher, url) DO NOTHING RETURNING id"""
                ),
                (doc.title, doc.publisher, doc.url),
            )
            return conn.execute(
                """SELECT id FROM documents WHERE title=%s AND publisher=%s AND url=%s""",
                (doc.title, doc.publisher, doc.url),
            ).fetchone()["id"]

    def documents(self) -> list[SourceDocument]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT * FROM documents ORDER BY id""").fetchall()
        return [
            SourceDocument(id=r["id"], title=r["title"], publisher=r["publisher"], url=r["url"])
            for r in rows
        ]

    def add_candidate(self, cand: PolicyCandidate) -> int:
        with self._connect() as conn:
            conn.execute(
                """SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))""",
                (f"candidate:{cand.document_id}:{cand.source_page}:{cand.text}",),
            )
            row = conn.execute(
                """SELECT id FROM candidates WHERE document_id=%s AND source_page=%s AND text=%s""",
                (cand.document_id, cand.source_page, cand.text),
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                (
                    """INSERT INTO candidates(document_id, suggested_type, text, normalized_title,
                    source_page, source_excerpt, code, excerpt_on_page, responsible_org,
                    timeframe, deadline_year, unit, target_value) VALUES (%s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
                ),
                (
                    cand.document_id,
                    cand.suggested_type.value,
                    cand.text,
                    cand.normalized_title,
                    cand.source_page,
                    cand.source_excerpt,
                    cand.code,
                    None if cand.excerpt_on_page is None else bool(cand.excerpt_on_page),
                    cand.responsible_org,
                    cand.timeframe,
                    cand.deadline_year,
                    cand.unit,
                    cand.target_value,
                ),
            )
            return cur.fetchone()["id"]

    def candidates(self, status: ReviewStatus | None = None) -> list[PolicyCandidate]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """SELECT * FROM candidates WHERE review_status=%s ORDER BY source_page""",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute("""SELECT * FROM candidates ORDER BY source_page""").fetchall()
        return [to_candidate(r) for r in rows]

    def candidate(self, candidate_id: int) -> PolicyCandidate | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM candidates WHERE id=%s""", (candidate_id,)
            ).fetchone()
        return to_candidate(row) if row else None

    def set_candidate_status(self, candidate_id: int, status: ReviewStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE candidates SET review_status=%s WHERE id=%s""",
                (status.value, candidate_id),
            )

    def add_commitment(self, com: Commitment) -> int:
        with self._connect() as conn:
            conn.execute(
                """SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))""",
                (f"commitment:{com.candidate_id}",),
            )
            if com.candidate_id is not None:
                row = conn.execute(
                    """SELECT id FROM commitments WHERE candidate_id=%s""", (com.candidate_id,)
                ).fetchone()
                if row:
                    return row["id"]
            cur = conn.execute(
                (
                    """INSERT INTO commitments(candidate_id, parent_id, kind, title, summary, code,
                    responsible_org, timeframe, deadline_year, unit, target_value, source_page,
                    asset_owner_jurisdiction)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
                ),
                (
                    com.candidate_id,
                    com.parent_id,
                    com.kind.value,
                    com.title,
                    com.summary,
                    com.code,
                    com.responsible_org,
                    com.timeframe,
                    com.deadline_year,
                    com.unit,
                    com.target_value,
                    com.source_page,
                    com.asset_owner_jurisdiction.value,
                ),
            )
            return cur.fetchone()["id"]

    def set_commitment_jurisdiction(self, commitment_id: int,
                                    jurisdiction: Jurisdiction) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE commitments SET asset_owner_jurisdiction=%s WHERE id=%s""",
                (jurisdiction.value, commitment_id))

    def language_profile(self, code: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT profile FROM language_profiles WHERE code=%s",
                               (code,)).fetchone()
        return json.loads(row["profile"]) if row else None

    def put_language_profile(self, code: str, profile: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO language_profiles(code, profile, updated_at) VALUES (%s, %s, now())"
                " ON CONFLICT(code) DO UPDATE SET profile=excluded.profile,"
                " updated_at=excluded.updated_at",
                (code, json.dumps(profile, ensure_ascii=False)))

    def commitments(self, kind: CandidateType | None = None) -> list[Commitment]:
        with self._connect() as conn:
            if kind:
                rows = conn.execute(
                    """SELECT * FROM commitments WHERE kind=%s ORDER BY code, id""", (kind.value,)
                ).fetchall()
            else:
                rows = conn.execute("""SELECT * FROM commitments ORDER BY code, id""").fetchall()
        return [to_commitment(r) for r in rows]

    def commitment(self, commitment_id: int) -> Commitment | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM commitments WHERE id=%s""", (commitment_id,)
            ).fetchone()
        return to_commitment(row) if row else None


class PostgresEvidenceRepository(_Repo):
    """evidence, links, budgets"""

    def official_sources(self) -> list[OfficialSource]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM official_sources ORDER BY sort_order, id"""
            ).fetchall()
        return [to_official_source(r) for r in rows]

    def upsert_official_source(self, src: OfficialSource) -> None:
        with self._connect() as conn:
            conn.execute(
                (
                    """INSERT INTO official_sources(url, title, publisher, sort_order, jurisdiction)
                    VALUES(%s,%s,%s,%s,%s) ON CONFLICT(url) DO UPDATE SET title=excluded.title,
                    publisher=excluded.publisher, sort_order=excluded.sort_order,
                    jurisdiction=COALESCE(excluded.jurisdiction, official_sources.jurisdiction)
                    RETURNING id"""
                ),
                (src.url, src.title, src.publisher, src.sort_order,
                 src.jurisdiction.value if src.jurisdiction else None),
            )

    def reviewed_evidence_id(self, commitment_id: int, url: str) -> int | None:
        """evidence id a reviewer already decided on, if any"""
        with self._connect() as conn:
            row = conn.execute(
                (
                    """SELECT e.id FROM evidence e JOIN links l ON l.evidence_id = e.id WHERE
                    e.commitment_id = %s AND e.url = %s AND l.review_status != 'unreviewed'
                    LIMIT 1"""
                ),
                (commitment_id, url),
            ).fetchone()
        return row["id"] if row else None

    def add_evidence(self, ev: EvidenceItem) -> int:
        with self._connect() as conn:
            conn.execute(
                (
                    """INSERT INTO evidence(commitment_id, url, title, publisher, published_on,
                    snippet, organisations, locations, dates_mentioned, status_hint,
                    status_excerpt, polarity, flags, procurement_ids, parcels)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON
                    CONFLICT(commitment_id, url) DO UPDATE SET snippet=excluded.snippet,
                    status_hint=excluded.status_hint, status_excerpt=excluded.status_excerpt,
                    polarity=excluded.polarity, flags=excluded.flags,
                    procurement_ids=excluded.procurement_ids, parcels=excluded.parcels
                    WHERE NOT EXISTS ( SELECT 1 FROM links l WHERE l.evidence_id = evidence.id
                    AND l.review_status != 'unreviewed') RETURNING id"""
                ),
                (
                    ev.commitment_id,
                    ev.url,
                    ev.title,
                    ev.publisher,
                    ev.published_on.isoformat() if ev.published_on else None,
                    ev.snippet,
                    json.dumps(ev.organisations, ensure_ascii=False),
                    json.dumps(ev.locations, ensure_ascii=False),
                    json.dumps(ev.dates_mentioned, ensure_ascii=False),
                    ev.status_hint.value,
                    ev.status_excerpt,
                    ev.polarity.value,
                    json.dumps(ev.flags),
                    json.dumps(ev.procurement_ids),
                    json.dumps(ev.parcels),
                ),
            )
            row = conn.execute(
                """SELECT id FROM evidence WHERE commitment_id=%s AND url=%s""",
                (ev.commitment_id, ev.url),
            ).fetchone()
            return row["id"]

    def evidence(self, evidence_id: int) -> EvidenceItem | None:
        with self._connect() as conn:
            row = conn.execute("""SELECT * FROM evidence WHERE id=%s""", (evidence_id,)).fetchone()
        return to_evidence(row) if row else None

    def evidence_many(self, ids: list[int]) -> dict[int, EvidenceItem]:
        """one query, not one per link"""
        if not ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM evidence WHERE id=ANY(%s)", (ids,)).fetchall()
        return {r["id"]: to_evidence(r) for r in rows}

    def add_link(self, link: EvidenceLink) -> int:
        with self._connect() as conn:
            conn.execute(
                (
                    """INSERT INTO links(commitment_id, evidence_id, score, similarity,
                    shared_organisations, shared_locations, shared_dates,
                    suggested_relationship, reasons) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(commitment_id, evidence_id) DO UPDATE SET score=excluded.score,
                    suggested_relationship=excluded.suggested_relationship,
                    reasons=excluded.reasons WHERE links.review_status = 'unreviewed' RETURNING
                    id"""
                ),
                (
                    link.commitment_id,
                    link.evidence_id,
                    link.score,
                    link.features.semantic_similarity,
                    json.dumps(link.features.shared_organisations, ensure_ascii=False),
                    json.dumps(link.features.shared_locations, ensure_ascii=False),
                    json.dumps(link.features.shared_dates, ensure_ascii=False),
                    link.suggested_relationship.value,
                    json.dumps(link.reasons, ensure_ascii=False),
                ),
            )
            row = conn.execute(
                """SELECT id FROM links WHERE commitment_id=%s AND evidence_id=%s""",
                (link.commitment_id, link.evidence_id),
            ).fetchone()
            return row["id"]

    def links(self, status: ReviewStatus | None = None) -> list[EvidenceLink]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """SELECT * FROM links WHERE review_status=%s ORDER BY score DESC""",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute("""SELECT * FROM links ORDER BY score DESC""").fetchall()
        return [to_link(r) for r in rows]

    def links_for(self, commitment_id: int) -> list[EvidenceLink]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM links WHERE commitment_id=%s ORDER BY score DESC""",
                (commitment_id,),
            ).fetchall()
        return [to_link(r) for r in rows]

    def link(self, link_id: int) -> EvidenceLink | None:
        with self._connect() as conn:
            row = conn.execute("""SELECT * FROM links WHERE id=%s""", (link_id,)).fetchone()
        return to_link(row) if row else None

    def decide_link(
        self, link_id: int, status: ReviewStatus, relationship: RelationshipType | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE links SET review_status=%s, relationship=%s WHERE id=%s""",
                (status.value, relationship.value if relationship else None, link_id),
            )

    def add_budget(self, b: BudgetRecord) -> int:
        with self._connect() as conn:
            conn.execute(
                """SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))""",
                (f"budget:{b.evidence_id}",),
            )
            row = conn.execute(
                (
                    """SELECT id FROM budgets WHERE evidence_id=%s AND kind=%s AND amount_raw=%s
                    AND fiscal_year IS NOT DISTINCT FROM %s AND description=%s AND currency=%s"""
                ),
                (b.evidence_id, b.kind.value, b.amount_raw, b.fiscal_year,
                 b.description, b.currency),
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                (
                    """INSERT INTO budgets(evidence_id, kind, amount_huf, amount_raw, fiscal_year,
                    description, source_url, currency, amount_native)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
                ),
                (
                    b.evidence_id,
                    b.kind.value,
                    b.amount_huf,
                    b.amount_raw,
                    b.fiscal_year,
                    b.description,
                    b.source_url,
                    b.currency,
                    b.amount_native,
                ),
            )
            return cur.fetchone()["id"]

    def budgets_for_evidence(self, evidence_id: int) -> list[BudgetRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM budgets WHERE evidence_id=%s ORDER BY id""", (evidence_id,)
            ).fetchall()
        return [to_budget(r) for r in rows]

    def budgets_many(self, evidence_ids: list[int]) -> dict[int, list[BudgetRecord]]:
        """one query, not one per evidence row"""
        if not evidence_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM budgets WHERE evidence_id=ANY(%s) ORDER BY id",
                (evidence_ids,),
            ).fetchall()
        out: dict[int, list[BudgetRecord]] = {}
        for r in rows:
            out.setdefault(r["evidence_id"], []).append(to_budget(r))
        return out

    # artifacts (m:n through evidence) + gazetteer

    def link_artifact(self, procurement_id: str, evidence_id: int,
                      polarity: EvidencePolarity) -> ImplementationArtifact:
        status = POLARITY_STATUS[polarity]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO implementation_artifacts(procurement_id) VALUES (%s)
                ON CONFLICT(procurement_id) DO NOTHING""", (procurement_id,))
            row = conn.execute(
                """SELECT * FROM implementation_artifacts WHERE procurement_id=%s FOR UPDATE""",
                (procurement_id,)).fetchone()
            if ARTIFACT_RANK[status] > ARTIFACT_RANK[ArtifactStatus(row["status"])]:
                row = conn.execute(
                    """UPDATE implementation_artifacts SET status=%s, status_evidence_id=%s,
                    updated_at=now() WHERE id=%s RETURNING *""",
                    (status.value, evidence_id, row["id"])).fetchone()
            conn.execute(
                """INSERT INTO artifact_evidence(artifact_id, evidence_id) VALUES (%s, %s)
                ON CONFLICT DO NOTHING""", (row["id"], evidence_id))
        return to_artifact(row)

    def artifacts_many(self, evidence_ids: list[int]
                       ) -> dict[int, list[ImplementationArtifact]]:
        if not evidence_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT ae.evidence_id, a.* FROM artifact_evidence ae JOIN
                implementation_artifacts a ON a.id = ae.artifact_id
                WHERE ae.evidence_id=ANY(%s)""", (evidence_ids,)).fetchall()
        out: dict[int, list[ImplementationArtifact]] = {}
        for r in rows:
            out.setdefault(r["evidence_id"], []).append(to_artifact(r))
        return out

    def resolve_parcel(self, parcel: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT canonical_name FROM places WHERE kind='parcel' AND name=%s
                ORDER BY confirmed DESC, id LIMIT 1""", (parcel,)).fetchone()
        return row["canonical_name"] if row else None

    def record_parcel(self, parcel: str, street: str, source: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO places(kind, name, canonical_name, source)
                VALUES ('parcel', %s, %s, %s) ON CONFLICT DO NOTHING""",
                (parcel, street, source))

    def upsert_place(self, kind: str, name: str, canonical_name: str, district: str,
                     osm_id: str | None, geojson: str | None, source: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO places(kind, name, canonical_name, district, osm_id, geojson,
                source, confirmed) VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                ON CONFLICT(kind, name, district) DO UPDATE SET osm_id=excluded.osm_id,
                geojson=excluded.geojson""",
                (kind, name, canonical_name, district, osm_id, geojson, source))

    def place_names(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT DISTINCT name FROM places WHERE kind != 'parcel'""").fetchall()
        return [r["name"] for r in rows]
