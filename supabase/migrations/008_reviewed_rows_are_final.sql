-- Paper Trail — re-runs can't rewrite rows a reviewer already decided on.
--
-- The api used to read review_status and then upsert, two requests apart;
-- a reviewer accepting in between could have the quote rewritten under
-- their decision. These functions do the check and the write in one
-- statement: ON CONFLICT ... DO UPDATE ... WHERE, so postgres evaluates the
-- reviewed state against the row it is about to update. Called over
-- PostgREST rpc from repositories/supabase_store.py.
--
-- Run once in the Supabase SQL editor, after 007_hybrid_or_query.sql.

create
or replace function upsert_evidence_unless_reviewed(r jsonb)
returns bigint
language plpgsql
set search_path = public
as $$
declare
ev_id bigint;
begin
insert into evidence as e (commitment_id, url, title, publisher, published_on,
                               snippet, organisations, locations, dates_mentioned,
                               status_hint, status_excerpt)
values ((r->>'commitment_id')::bigint, r->>'url', r->>'title', coalesce (r->>'publisher', ''), (r->>'published_on'):: date, coalesce (r->>'snippet', ''), coalesce (r->>'organisations', '[]'), coalesce (r->>'locations', '[]'), coalesce (r->>'dates_mentioned', '[]'), coalesce (r->>'status_hint', 'unknown'), r->>'status_excerpt')
on conflict (commitment_id, url) do
update set
    title = excluded.title, publisher = excluded.publisher,
    published_on = excluded.published_on, snippet = excluded.snippet,
    organisations = excluded.organisations, locations = excluded.locations,
    dates_mentioned = excluded.dates_mentioned,
    status_hint = excluded.status_hint, status_excerpt = excluded.status_excerpt
where not exists (
    select 1 from links l
    where l.evidence_id = e.id
  and l.review_status <> 'unreviewed')
    returning id
into ev_id;

if
ev_id is null then  -- blocked: the reviewed row stays, return its id
select id
into ev_id
from evidence
where commitment_id = (r ->>'commitment_id')::bigint and url = r->>'url';
end if;
return ev_id;
end;
$$;

create
or replace function upsert_link_unless_reviewed(r jsonb)
returns bigint
language plpgsql
set search_path = public
as $$
declare
link_id bigint;
begin
insert into links as l (commitment_id, evidence_id, score, similarity,
                            shared_organisations, shared_locations, shared_dates,
                            suggested_relationship, reasons)
values ((r->>'commitment_id')::bigint, (r->>'evidence_id')::bigint, coalesce ((r->>'score'):: double precision, 0), coalesce ((r->>'similarity'):: double precision, 0), coalesce (r->>'shared_organisations', '[]'), coalesce (r->>'shared_locations', '[]'), coalesce (r->>'shared_dates', '[]'), r->>'suggested_relationship', coalesce (r->>'reasons', '[]'))
on conflict (commitment_id, evidence_id) do
update set
    score = excluded.score, similarity = excluded.similarity,
    shared_organisations = excluded.shared_organisations,
    shared_locations = excluded.shared_locations,
    shared_dates = excluded.shared_dates,
    suggested_relationship = excluded.suggested_relationship,
    reasons = excluded.reasons
where l.review_status = 'unreviewed'
    returning id
into link_id;

if
link_id is null then
select id
into link_id
from links
where commitment_id = (r ->>'commitment_id')::bigint
           and evidence_id = (r->>'evidence_id')::bigint;
end if;
return link_id;
end;
$$;
