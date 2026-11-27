-- pages an extractor has finished, written in the same transaction as their candidates,
-- so a retried ingest job skips them instead of starting at page 1 again. keyed by the
-- extractor (model) too: a new model, or an llm configured after a rules-only run, reads
-- every page again. maintenance reset clears it with the other generated rows
create table if not exists document_ingest_pages
(
    document_id  bigint      not null references documents (id),
    extractor    text        not null,
    page_number  integer     not null,
    processed_at timestamptz not null default now(),
    primary key (document_id, extractor, page_number)
);

DO $$
BEGIN
  -- the api role runs jobs itself in JOB_MODE=internal
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT SELECT, INSERT ON document_ingest_pages TO paper_trail_api;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
    GRANT SELECT, INSERT ON document_ingest_pages TO paper_trail_worker;
  END IF;
END $$;
