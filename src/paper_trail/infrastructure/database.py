"""SQLite persistence. One file, no ORM, no server."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    url TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id),
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

CREATE TABLE IF NOT EXISTS commitments (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id),
    parent_id INTEGER REFERENCES commitments(id),
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

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY,
    commitment_id INTEGER NOT NULL REFERENCES commitments(id),
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
    UNIQUE(commitment_id, url)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    commitment_id INTEGER NOT NULL REFERENCES commitments(id),
    evidence_id INTEGER NOT NULL REFERENCES evidence(id),
    score REAL DEFAULT 0,
    similarity REAL DEFAULT 0,
    shared_organisations TEXT DEFAULT '[]',
    shared_locations TEXT DEFAULT '[]',
    shared_dates TEXT DEFAULT '[]',
    suggested_relationship TEXT NOT NULL,
    reasons TEXT DEFAULT '[]',
    relationship TEXT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    UNIQUE(commitment_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY,
    evidence_id INTEGER NOT NULL REFERENCES evidence(id),
    kind TEXT NOT NULL,
    amount_huf INTEGER,
    amount_raw TEXT DEFAULT '',
    fiscal_year INTEGER,
    description TEXT DEFAULT '',
    source_url TEXT DEFAULT ''
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
