alter table budgets add column if not exists currency text not null default 'HUF';
alter table budgets add column if not exists amount_native text;
-- durable leases + the db itself keeping workers away from review fields
alter table jobs add column if not exists locked_at timestamptz;
alter table jobs add column if not exists heartbeat_at timestamptz;
alter table jobs add column if not exists worker_id text;
alter table jobs add column if not exists lease_token text;
alter table jobs add column if not exists attempts integer not null default 0;
alter table jobs add column if not exists available_at timestamptz not null default now();
create index if not exists jobs_available_idx on jobs(available_at,created_at) where status='queued';
create unique index if not exists documents_natural_uq on documents(title,publisher,url);
create unique index if not exists candidates_receipt_uq on candidates(document_id,source_page,md5(text));
create unique index if not exists commitments_candidate_uq on commitments(candidate_id) where candidate_id is not null;
create unique index if not exists budgets_receipt_uq on budgets
(evidence_id,currency,kind,md5(amount_raw),coalesce(fiscal_year,-1),md5(description));
create table if not exists readiness_probe (id integer primary key, checked_at timestamptz not null);

-- column grants: workers can't insert or touch confirmed records
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT USAGE ON SCHEMA public TO paper_trail_api;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO paper_trail_api;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO paper_trail_api;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
    GRANT USAGE ON SCHEMA public TO paper_trail_worker;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO paper_trail_worker;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO paper_trail_worker;
    GRANT INSERT, UPDATE ON documents,pages,chunks,official_sources,jobs TO paper_trail_worker;
    GRANT DELETE ON chunks TO paper_trail_worker;
    GRANT INSERT ON budgets TO paper_trail_worker;
    GRANT INSERT (document_id,suggested_type,text,normalized_title,source_page,source_excerpt,
      code,excerpt_on_page,responsible_org,timeframe,deadline_year,unit,target_value)
      ON candidates TO paper_trail_worker;
    GRANT INSERT (commitment_id,url,title,publisher,published_on,snippet,organisations,locations,
      dates_mentioned,status_hint,status_excerpt),
      UPDATE (title,publisher,published_on,snippet,organisations,locations,dates_mentioned,status_hint,status_excerpt)
      ON evidence TO paper_trail_worker;
    GRANT INSERT (commitment_id,evidence_id,score,similarity,shared_organisations,shared_locations,
      shared_dates,suggested_relationship,reasons),
      UPDATE (score,similarity,shared_organisations,shared_locations,shared_dates,suggested_relationship,reasons)
      ON links TO paper_trail_worker;
  END IF;
END $$;

create or replace function protect_reviewed_worker_rows() returns trigger
language plpgsql as $$
begin
  if current_user = 'paper_trail_worker' then
    if TG_TABLE_NAME = 'links' then
      if old.review_status <> 'unreviewed' then
        raise exception 'workers cannot rewrite reviewed links';
      end if;
    elsif TG_TABLE_NAME = 'evidence' and exists
      (select 1 from links where evidence_id=old.id and review_status <> 'unreviewed') then
      raise exception 'workers cannot rewrite reviewed evidence';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists protect_reviewed_worker_links on links;
create trigger protect_reviewed_worker_links before update on links
for each row execute function protect_reviewed_worker_rows();
drop trigger if exists protect_reviewed_worker_evidence on evidence;
create trigger protect_reviewed_worker_evidence before update on evidence
for each row execute function protect_reviewed_worker_rows();

alter table chunks add column if not exists lemma_text text not null default '';
alter table chunks add column if not exists lemma_search tsvector
  generated always as (to_tsvector('simple'::regconfig,lemma_text)) stored;
create index if not exists chunks_lemma_search_gin on chunks using gin(lemma_search);

