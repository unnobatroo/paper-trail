-- plain-english notes on queue items: what the hungarian says, and an ai suggestion.
-- suggestions only, a note never decides anything. its own table so the review wall
-- on candidates/links stays untouched. written by the owner (maintenance notes import)
create table if not exists notes
(
    subject_kind text        not null check (subject_kind in ('candidate', 'link')),
    subject_id   bigint      not null,
    title_en     text        not null,
    summary_en   text        not null,
    suggestion   text        not null check (suggestion in ('accept', 'reject', 'unsure')),
    reason_en    text        not null default '',
    author       text        not null,
    updated_at   timestamptz not null default now(),
    primary key (subject_kind, subject_id)
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT SELECT ON notes TO paper_trail_api;
  END IF;
END $$;
