-- Paper Trail — hybrid retrieval: lexical (Hungarian tsvector) fused with
-- dense (pgvector cosine).
--
-- Why: on the benchmark corpus, dense-only retrieval reached src_recall@5
-- 0.369, stemmed lexical 0.577, and 50/50 min-max score fusion 0.588 —
-- Hungarian municipal text rewards morphological matching more than a
-- multilingual embedding captures. Reciprocal-rank fusion was evaluated and
-- rejected (it discards score magnitude and scored worse than dense alone).
--
-- Run once in the Supabase SQL editor, after 005_official_sources.sql.

-- Lexical index -------------------------------------------------------------
-- A stored tsvector over each chunk's text using the Hungarian stemmer, so
-- "fáit/fák/fákat" share a lexeme. GIN keeps lookups sub-linear.
-- NOTE: the corpus language is fixed at column build time — a deployment on
-- a different corpus language must regenerate this column with its own
-- regconfig (and set PAPER_TRAIL_LANGUAGE to match). The query side is
-- parameterized via lex_config so app config stays the single source.

alter table chunks
    add column if not exists tsv tsvector
    generated always as (to_tsvector('hungarian', text)) stored;

create index if not exists chunks_tsv_gin on chunks using gin(tsv);

-- Hybrid top-k --------------------------------------------------------------
-- Same contract as match_chunks (candidate set = chunks of the fetched
-- pages, same return shape) but similarity = lex_weight * norm(ts_rank)
-- + (1 - lex_weight) * norm(cosine), where norm() min-max-normalizes each
-- signal across the candidate set. Degenerate cases degrade cleanly: an
-- empty/zero-hit lexical side collapses to dense-only and vice versa.

create or replace function match_chunks_hybrid(
    query_embedding vector(1024),
    query_text text,
    model text,
    match_count integer,
    page_urls text[] default null,
    lex_weight double precision default 0.5,
    lex_config regconfig default 'hungarian'
)
returns table(page_id bigint, page_url text,
              chunk_text text, similarity double precision)
language sql stable
set search_path = public
as $$
    with scored as (
        select c.page_id,
               p.url as page_url,
               c.text as chunk_text,
               1 - (c.embedding <=> query_embedding) as dense,
               ts_rank(c.tsv, websearch_to_tsquery(lex_config, query_text))
                   as lex
          from chunks c
          join pages p on p.id = c.page_id
         where c.embed_model = model
           and (page_urls is null or p.url = any(page_urls))
    ),
    bounds as (
        select min(dense) as dmin, max(dense) as dmax,
               min(lex) as lmin, max(lex) as lmax
          from scored
    )
    select scored.page_id,
           scored.page_url,
           scored.chunk_text,
           lex_weight * (scored.lex - bounds.lmin)
               / greatest(bounds.lmax - bounds.lmin, 1e-9)
         + (1 - lex_weight) * (scored.dense - bounds.dmin)
               / greatest(bounds.dmax - bounds.dmin, 1e-9)
           as similarity
      from scored, bounds
     order by similarity desc
     limit match_count;
$$;
