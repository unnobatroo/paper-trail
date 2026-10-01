-- Paper Trail phase 1 — system caches live in Postgres, not on disk.
--
-- `pages`    fetched official pages (replaces data/processed/fetched/*.txt)
-- `chunks`   per-page chunk embeddings (replaces fetched/embeddings/*.json)
-- `match_chunks`  top-k cosine retrieval over those chunks via pgvector
--
-- Run once in the Supabase SQL editor, after 001_schema.sql.
-- Needs: Dashboard → Database → Extensions → vector (or the line below).

create extension if not exists vector;

-- Fetched pages -----------------------------------------------------------
-- Text is immutable per row: a page is fetched once and reused by every
-- later evidence search, across commitments.

create table if not exists pages (
    id bigint generated always as identity primary key,
    url text unique not null,
    title text not null default '',
    text text not null,
    published_on date,
    fetched_at timestamptz not null default now()
);

-- Chunk embeddings --------------------------------------------------------
-- One row per (page, model, chunk). Vectors are stored in a fixed-width
-- vector(1024) column: shorter model outputs are right-padded with zeros,
-- which leaves cosine similarity unchanged (padding adds nothing to the
-- dot product or the norms). embed_model prevents mixing vector spaces.

create table if not exists chunks (
    id bigint generated always as identity primary key,
    page_id bigint not null references pages(id) on delete cascade,
    embed_model text not null,
    chunk_index integer not null,
    text text not null,
    embedding vector(1024) not null,
    unique(page_id, embed_model, chunk_index)
);

create index if not exists chunks_embed_model_idx on chunks(embed_model);

-- hnsw keeps top-k sub-linear once the corpus grows past a few hundred pages.
-- exact search is fine below that — the index is advisory, not required.
create index if not exists chunks_embedding_hnsw
    on chunks using hnsw (embedding vector_cosine_ops);

-- Top-k cosine retrieval --------------------------------------------------
-- Equivalent to the old in-Python "score every chunk, sort, take top-k",
-- executed in the database. page_urls restricts the candidate set to the
-- pages fetched for the current evidence run (same semantics as before).

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

-- Source documents --------------------------------------------------------
-- Seed PDFs (the climate strategy and friends) live in Storage, not the
-- repo. Private bucket; the API reads it with the service key.

insert into storage.buckets (id, name, public)
values ('source-documents', 'source-documents', false)
on conflict (id) do nothing;
