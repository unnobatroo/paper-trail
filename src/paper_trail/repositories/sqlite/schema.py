"""sqlite, one file, no orm"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
         CREATE TABLE IF NOT EXISTS documents
         (
             id
             INTEGER
             PRIMARY
             KEY,
             title
             TEXT
             NOT
             NULL,
             publisher
             TEXT
             NOT
             NULL,
             url
             TEXT
             DEFAULT
             ''
         );

         CREATE TABLE IF NOT EXISTS candidates
         (
             id
             INTEGER
             PRIMARY
             KEY,
             document_id
             INTEGER
             NOT
             NULL
             REFERENCES
             documents
         (
             id
         ),
             suggested_type TEXT NOT NULL,
             text TEXT NOT NULL,
             normalized_title TEXT NOT NULL,
             source_page INTEGER NOT NULL,
             source_excerpt TEXT NOT NULL,
             code TEXT,
             excerpt_on_page INTEGER,
             responsible_org TEXT,
             timeframe TEXT,
             deadline_year INTEGER,
             unit TEXT,
             target_value REAL,
             review_status TEXT NOT NULL DEFAULT 'unreviewed'
             );

         CREATE TABLE IF NOT EXISTS commitments
         (
             id
             INTEGER
             PRIMARY
             KEY,
             candidate_id
             INTEGER
             REFERENCES
             candidates
         (
             id
         ),
             parent_id INTEGER REFERENCES commitments
         (
             id
         ),
             kind TEXT NOT NULL,
             title TEXT NOT NULL,
             summary TEXT DEFAULT '',
             code TEXT,
             responsible_org TEXT,
             timeframe TEXT,
             deadline_year INTEGER,
             unit TEXT,
             target_value REAL,
             source_page INTEGER
             );

         CREATE TABLE IF NOT EXISTS evidence
         (
             id
             INTEGER
             PRIMARY
             KEY,
             commitment_id
             INTEGER
             NOT
             NULL
             REFERENCES
             commitments
         (
             id
         ),
             url TEXT NOT NULL,
             title TEXT NOT NULL,
             publisher TEXT DEFAULT '',
             published_on TEXT,
             snippet TEXT DEFAULT '',
             organisations TEXT DEFAULT '[]',
             locations TEXT DEFAULT '[]',
             dates_mentioned TEXT DEFAULT '[]',
             status_hint TEXT DEFAULT 'unknown',
             status_excerpt TEXT,
             UNIQUE
         (
             commitment_id,
             url
         )
             );

         CREATE TABLE IF NOT EXISTS links
         (
             id
             INTEGER
             PRIMARY
             KEY,
             commitment_id
             INTEGER
             NOT
             NULL
             REFERENCES
             commitments
         (
             id
         ),
             evidence_id INTEGER NOT NULL REFERENCES evidence
         (
             id
         ),
             score REAL DEFAULT 0,
             similarity REAL DEFAULT 0,
             shared_organisations TEXT DEFAULT '[]',
             shared_locations TEXT DEFAULT '[]',
             shared_dates TEXT DEFAULT '[]',
             suggested_relationship TEXT NOT NULL,
             reasons TEXT DEFAULT '[]',
             relationship TEXT,
             review_status TEXT NOT NULL DEFAULT 'unreviewed',
             UNIQUE
         (
             commitment_id,
             evidence_id
         )
             );

         CREATE TABLE IF NOT EXISTS budgets
         (
             id
             INTEGER
             PRIMARY
             KEY,
             evidence_id
             INTEGER
             NOT
             NULL
             REFERENCES
             evidence
         (
             id
         ),
             kind TEXT NOT NULL,
             amount_huf INTEGER,
             currency TEXT NOT NULL DEFAULT 'HUF',
             amount_native TEXT,
             amount_raw TEXT DEFAULT '',
             fiscal_year INTEGER,
             description TEXT DEFAULT '',
             source_url TEXT DEFAULT ''
             );

         -- The evidence-search source catalogue. Seeded in Postgres by migration
-- 005; the local backend leaves it empty and search relies on the web
-- provider alone.
         CREATE TABLE IF NOT EXISTS official_sources
         (
             id
             INTEGER
             PRIMARY
             KEY,
             url
             TEXT
             NOT
             NULL
             UNIQUE,
             title
             TEXT
             NOT
             NULL
             DEFAULT
             '',
             publisher
             TEXT
             NOT
             NULL
             DEFAULT
             '',
             sort_order
             INTEGER
             NOT
             NULL
             DEFAULT
             0
         );

         -- Enforce the natural key add_document dedupes on (also upgrades DBs
-- created before this index existed).
         CREATE UNIQUE INDEX IF NOT EXISTS documents_natural_uq
             ON documents(title, publisher, url);

         -- same shape as db/sql/010_accountability.sql
         CREATE TABLE IF NOT EXISTS implementation_artifacts (
             id INTEGER PRIMARY KEY,
             procurement_id TEXT NOT NULL UNIQUE,
             status TEXT NOT NULL DEFAULT 'active',
             status_evidence_id INTEGER REFERENCES evidence(id),
             updated_at TEXT
         );
         CREATE TABLE IF NOT EXISTS artifact_evidence (
             artifact_id INTEGER NOT NULL REFERENCES implementation_artifacts(id),
             evidence_id INTEGER NOT NULL REFERENCES evidence(id),
             PRIMARY KEY (artifact_id, evidence_id)
         );
         CREATE TABLE IF NOT EXISTS language_profiles (
             code TEXT PRIMARY KEY,
             profile TEXT NOT NULL,
             updated_at TEXT
         );
         CREATE TABLE IF NOT EXISTS notes (
             subject_kind TEXT NOT NULL CHECK (subject_kind IN ('candidate', 'link')),
             subject_id INTEGER NOT NULL,
             title_en TEXT NOT NULL,
             summary_en TEXT NOT NULL,
             suggestion TEXT NOT NULL CHECK (suggestion IN ('accept', 'reject', 'unsure')),
             reason_en TEXT NOT NULL DEFAULT '',
             author TEXT NOT NULL,
             updated_at TEXT,
             PRIMARY KEY (subject_kind, subject_id)
         );
         CREATE TABLE IF NOT EXISTS places (
             id INTEGER PRIMARY KEY,
             kind TEXT NOT NULL,
             name TEXT NOT NULL,
             canonical_name TEXT NOT NULL,
             district TEXT NOT NULL DEFAULT '',
             osm_id TEXT,
             geojson TEXT,
             source TEXT NOT NULL,
             confirmed INTEGER NOT NULL DEFAULT 0,
             UNIQUE (kind, name, district)
         ); \
         """


def connect(db_path: Path | str) -> sqlite3.Connection:
    """fresh connection, caller closes it

    sqlite3 objects are stuck to the thread that made them, so nothing long-lived
    (app state, worker threads) may hold one
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str) -> None:
    """create the schema if missing, safe to call every boot"""
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(budgets)")}
        if "currency" not in columns:
            conn.execute("ALTER TABLE budgets ADD COLUMN currency TEXT NOT NULL DEFAULT 'HUF'")
        if "amount_native" not in columns:
            conn.execute("ALTER TABLE budgets ADD COLUMN amount_native TEXT")
        # migration 010, sqlite edition
        ev_cols = {r["name"] for r in conn.execute("PRAGMA table_info(evidence)")}
        for col, default in (("polarity", "'affirmative'"), ("flags", "'[]'"),
                             ("procurement_ids", "'[]'"), ("parcels", "'[]'")):
            if col not in ev_cols:
                conn.execute(f"ALTER TABLE evidence ADD COLUMN {col} TEXT NOT NULL"
                             f" DEFAULT {default}")
        src_cols = {r["name"] for r in conn.execute("PRAGMA table_info(official_sources)")}
        if "jurisdiction" not in src_cols:
            conn.execute("ALTER TABLE official_sources ADD COLUMN jurisdiction TEXT")
        com_cols = {r["name"] for r in conn.execute("PRAGMA table_info(commitments)")}
        if "asset_owner_jurisdiction" not in com_cols:
            conn.execute("ALTER TABLE commitments ADD COLUMN asset_owner_jurisdiction TEXT"
                         " NOT NULL DEFAULT 'district_municipality'")
        conn.execute("UPDATE budgets SET kind='initial_appropriation'"
                     " WHERE kind='approved_allocation'")
        conn.commit()
    finally:
        conn.close()
