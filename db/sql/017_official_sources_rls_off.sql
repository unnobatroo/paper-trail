-- 005 turned on row-level security for official_sources; its policies lived in the
-- Supabase-only 004, which the alembic baseline skips. RLS with no policies hides every
-- row from every role but the owner, so the worker read an empty registry and evidence
-- search found nothing. Access here is role grants (009), like every other table.
alter table official_sources disable row level security;
