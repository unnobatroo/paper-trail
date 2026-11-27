-- sql nothing calls anymore. retrieval lives in repositories/index.py: one dense and one
-- lexical query, fused with reciprocal rank fusion in python. that replaced the min-max
-- fusion in match_chunks_hybrid (006/007), whose comment about rrf losing describes that
-- older benchmark, not the running code. the upsert functions (008) served the removed
-- supabase store; repositories/store.py does the same ON CONFLICT ... WHERE inline

drop function if exists match_chunks(vector, text, integer, text[]);
drop function if exists match_chunks_hybrid(vector, text, text, integer, text[],
                                             double precision, regconfig);
drop function if exists upsert_evidence_unless_reviewed(jsonb);
drop function if exists upsert_link_unless_reviewed(jsonb);

-- hungarian-only stemmed column, computed on every chunk insert and never read: prod
-- searches lemma_search (huspacy), otherwise the query stems with the profile's own
-- ts_config over the few hundred chunks of the pages fetched for that run
drop index if exists chunks_tsv_gin;
alter table chunks drop column if exists tsv;
