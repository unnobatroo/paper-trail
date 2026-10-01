-- Paper Trail — lock down the Data API.
--
-- The browser only ever talks to the FastAPI service, which uses the
-- service-role key (BYPASSRLS) server-side. Nothing public should touch
-- PostgREST directly, so enable RLS on every app table and create no
-- policies: anon/authenticated get denied on every statement while the
-- backend keeps working unchanged.

begin;

alter table public.documents enable row level security;
alter table public.candidates enable row level security;
alter table public.commitments enable row level security;
alter table public.evidence enable row level security;
alter table public.links enable row level security;
alter table public.budgets enable row level security;
alter table public.pages enable row level security;
alter table public.chunks enable row level security;
alter table public.jobs enable row level security;

-- Pin match_chunks to the public schema so role-mutable search_path can't
-- redirect its table/operator resolution (Supabase advisor lint 0011).
create or replace function match_chunks(
    query_embedding vector(1024),
    model text,
    match_count integer,
    page_urls text[] default null
)
returns table(page_id bigint, page_url text,
              chunk_text text, similarity double precision)
language sql stable
set search_path = public
as $$
    select c.page_id,
           p.url as page_url,
           c.text as chunk_text,
           1 - (c.embedding <=> query_embedding) as similarity
      from chunks c
      join pages p on p.id = c.page_id
     where c.embed_model = model
       and (page_urls is null or p.url = any(page_urls))
     order by c.embedding <=> query_embedding
     limit match_count;
$$;

commit;
