-- Paper Trail — the official-source catalogue moves from code to the DB,
-- plus the indexes Postgres doesn't create for foreign keys.
--
-- official_sources: pages the evidence search always fetches and reads
-- (formerly the OFFICIAL_DOCS constant in sources/official_docs.py — data
-- belongs in the database, the code only operates on it). Rows are
-- managed directly in the database — none live in the repo.
--
-- Run once in the Supabase SQL editor, after 004_rls.sql.

begin;

create table if not exists official_sources (
    id bigint generated always as identity primary key,
    url text unique not null,
    title text not null default '',
    publisher text not null default '',
    sort_order integer not null default 0
);

alter table public.official_sources enable row level security;

-- Referencing-side indexes: Postgres never indexes the FK column itself.
-- evidence.commitment_id and links.commitment_id are already covered by the
-- leftmost column of their unique constraints.
create index if not exists candidates_document_id_idx
    on candidates(document_id);
create index if not exists commitments_candidate_id_idx
    on commitments(candidate_id);
create index if not exists commitments_parent_id_idx
    on commitments(parent_id);
create index if not exists links_evidence_id_idx
    on links(evidence_id);
create index if not exists budgets_evidence_id_idx
    on budgets(evidence_id);
create index if not exists chunks_page_id_idx
    on chunks(page_id);

-- Enforce the natural key the repository dedupes on, so a concurrent
-- insert can't double-register a document.
create unique index if not exists documents_natural_uq
    on documents(title, publisher, url);

commit;
