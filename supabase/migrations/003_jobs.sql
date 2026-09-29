-- Paper Trail — durable background jobs.
--
-- A job is data (kind + JSON payload), not a closure, so any API worker
-- can claim it. Claiming is a conditional UPDATE (queued → running),
-- which PostgREST executes atomically — a job can't be run by two
-- workers. updated_at is rewritten on every progress/result write; a
-- running job that stops updating is assumed dead by the sweeper.

create table if not exists jobs (
    id text primary key,
    kind text not null,
    payload jsonb not null default '{}',
    dedupe_key text not null,
    status text not null default 'queued'
        check (status in ('queued', 'running', 'done', 'failed')),
    progress text not null default '',
    result jsonb,
    error text,
    claimed_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- one job of a given kind+payload in flight at a time — resubmitting
-- "Find evidence" for the same commitment attaches to the in-flight job
-- instead of duplicating the work
create unique index if not exists jobs_inflight_uq
    on jobs(dedupe_key) where status in ('queued', 'running');

create index if not exists jobs_queued_idx
    on jobs(created_at) where status = 'queued';
create index if not exists jobs_stale_idx
    on jobs(updated_at) where status = 'running';
