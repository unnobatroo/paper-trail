-- Paper Trail — Postgres schema for Supabase.
-- Mirrors the SQLite schema in src/paper_trail/infrastructure/database.py.
-- Run once in the Supabase SQL editor (Dashboard → SQL → New query).
-- List columns are TEXT holding JSON arrays, same as the SQLite backend.

create table if not exists documents (
    id bigint generated always as identity primary key,
    title text not null,
    publisher text not null,
    url text default ''
);

create table if not exists candidates (
    id bigint generated always as identity primary key,
    document_id bigint not null references documents(id),
    suggested_type text not null,
    text text not null,
    normalized_title text not null,
    source_page integer not null,
    source_excerpt text not null,
    code text,
    excerpt_on_page boolean,
    responsible_org text,
    timeframe text,
    deadline_year integer,
    unit text,
    target_value double precision,
    review_status text not null default 'unreviewed'
);

create table if not exists commitments (
    id bigint generated always as identity primary key,
    candidate_id bigint references candidates(id),
    parent_id bigint references commitments(id),
    kind text not null,
    title text not null,
    summary text default '',
    code text,
    responsible_org text,
    timeframe text,
    deadline_year integer,
    unit text,
    target_value double precision,
    source_page integer
);

create table if not exists evidence (
    id bigint generated always as identity primary key,
    commitment_id bigint not null references commitments(id),
    url text not null,
    title text not null,
    publisher text default '',
    published_on date,
    snippet text default '',
    organisations text default '[]',
    locations text default '[]',
    dates_mentioned text default '[]',
    status_hint text default 'unknown',
    status_excerpt text,
    unique(commitment_id, url)
);

create table if not exists links (
    id bigint generated always as identity primary key,
    commitment_id bigint not null references commitments(id),
    evidence_id bigint not null references evidence(id),
    score double precision default 0,
    similarity double precision default 0,
    shared_organisations text default '[]',
    shared_locations text default '[]',
    shared_dates text default '[]',
    suggested_relationship text not null,
    reasons text default '[]',
    relationship text,
    review_status text not null default 'unreviewed',
    unique(commitment_id, evidence_id)
);

create table if not exists budgets (
    id bigint generated always as identity primary key,
    evidence_id bigint not null references evidence(id),
    kind text not null,
    amount_huf bigint,
    amount_raw text default '',
    fiscal_year integer,
    description text default '',
    source_url text default ''
);
