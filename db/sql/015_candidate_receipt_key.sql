-- candidates dedupe on the verbatim receipt, not on the llm's paraphrase. 009 keyed on
-- md5(text), so a re-run that worded the same passage differently stored it twice and a
-- rejected candidate could come back as new. whitespace doesn't count, same rule as the
-- receipt check in ml/extraction.py (pdf text has spaces inside words).
-- one receipt per page is what extraction's dedupe already keeps within a run.
-- ingestion drops blank receipts, so every stored row has one to key on

DO $$
DECLARE
  clashes integer;
BEGIN
  SELECT count(*) INTO clashes FROM (
    SELECT 1 FROM candidates
     GROUP BY document_id, source_page, md5(regexp_replace(source_excerpt, '\s', '', 'g'))
    HAVING count(*) > 1) d;
  -- reviewed rows and commitments may hang off either copy, a person merges them.
  -- no percent-format: alembic runs this through psycopg, which reads it as a placeholder
  IF clashes > 0 THEN
    RAISE EXCEPTION USING MESSAGE = clashes
      || ' pages have two candidates quoting the same receipt, merge them first';
  END IF;
END $$;

drop index if exists candidates_receipt_uq;
create unique index if not exists candidates_excerpt_uq on candidates
  (document_id, source_page, md5(regexp_replace(source_excerpt, '\s', '', 'g')));
