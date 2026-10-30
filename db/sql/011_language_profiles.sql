-- language profiles live here, not in code. one json document per language code,
-- managed with python -m paper_trail.maintenance profile import FILE
create table if not exists language_profiles
(
    code       text primary key,
    profile    text        not null,
    updated_at timestamptz not null default now()
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT SELECT ON language_profiles TO paper_trail_api;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
    GRANT SELECT ON language_profiles TO paper_trail_worker;
  END IF;
END $$;
