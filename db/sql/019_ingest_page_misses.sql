-- pages the model answered with nothing usable (bad json, a failed request on a half) are not
-- checkpointed, so every run read them again, forever when the page always fails. this counts
-- the misses per page; ingest stops asking once a page reaches its cap and says so.
-- keyed like the checkpoints (extractor, pdf bytes), so a new model or a revised pdf starts
-- clean. maintenance reset clears it with them
create table if not exists document_ingest_misses
(
    document_id bigint  not null references documents (id),
    extractor   text    not null,
    content_sha text    not null,
    page_number integer not null,
    misses      integer not null default 1,
    primary key (document_id, extractor, content_sha, page_number)
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON document_ingest_misses TO paper_trail_api;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON document_ingest_misses TO paper_trail_worker;
  END IF;
END $$;
