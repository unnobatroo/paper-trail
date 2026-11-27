-- ingest checkpoints are keyed by the pdf's content too. add_document hands back the same
-- id for the same title, publisher and url, so a town that replaced its pdf at that url kept
-- the old checkpoints and its revised pages were never read. a checkpoint now counts only for
-- the bytes it was made from.
-- rows written before this have content_sha = '' and stay trusted for any content, as they
-- were, so the upgrade doesn't send every document back to the model. maintenance reset
-- clears them with the other generated rows

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_name = 'document_ingest_pages'
                    AND column_name = 'content_sha') THEN
    ALTER TABLE document_ingest_pages ADD COLUMN content_sha text NOT NULL DEFAULT '';
    ALTER TABLE document_ingest_pages DROP CONSTRAINT document_ingest_pages_pkey;
    ALTER TABLE document_ingest_pages
      ADD PRIMARY KEY (document_id, extractor, content_sha, page_number);
  END IF;
END $$;
