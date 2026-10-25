-- Paper Trail — hybrid retrieval, lexical side fixed to OR semantics.
--
-- 006 ranked chunks against websearch_to_tsquery(query_text), which ANDs
-- every term. The query is a commitment's title + summary + code, so no
-- chunk ever contains all of it: ts_rank came back ~1e-20 everywhere, the
-- min-max normalisation flattened it, and production silently ran
-- dense-only. The file backend (and the 0.588 benchmark) score lexical
-- overlap OR-style, so this brings Postgres in line with what was measured.
--
-- Checked on Postgres 18 with the hungarian config: the same query and
-- chunk rank 1e-20 under 006 and 0.020 here.
--
-- Run once in the Supabase SQL editor, after 006_hybrid_search.sql.

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
    with q as (
        -- stem once with the corpus config, then OR the lexemes. the cast
        -- (not to_tsquery) keeps them from being stemmed a second time
        select replace(plainto_tsquery(lex_config, query_text)::text,
                       '&', '|')::tsquery as lexemes
    ),
    scored as (
        select c.page_id,
               p.url as page_url,
               c.text as chunk_text,
               1 - (c.embedding <=> query_embedding) as dense,
               ts_rank(c.tsv, q.lexemes) as lex
          from chunks c
          join pages p on p.id = c.page_id
          cross join q
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
