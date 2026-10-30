-- polarity, artifacts (m:n), 5-state money, asset owner, gazetteer.
-- workers only ever add hints, never decisions

alter table evidence add column if not exists polarity text not null default 'affirmative';
alter table evidence add column if not exists flags text not null default '[]';
alter table evidence add column if not exists procurement_ids text not null default '[]';
alter table evidence add column if not exists parcels text not null default '[]';
alter table commitments add column if not exists asset_owner_jurisdiction text not null
  default 'district_municipality';
-- registry rows for an owner's own sites (utility, city), null = always searched.
-- routing is data, not code: python -m paper_trail.maintenance source add
alter table official_sources add column if not exists jurisdiction text;

-- grant award / decree allocation = initial appropriation now
update budgets set kind = 'initial_appropriation' where kind = 'approved_allocation';

-- contract/lot/funded project, keyed by its official id (ekr or eu code)
create table if not exists implementation_artifacts
(
    id                 bigint generated always as identity primary key,
    procurement_id     text        not null unique,
    status             text        not null default 'active'
        check (status in ('active', 'amended', 'terminated')),
    status_evidence_id bigint references evidence (id),
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

-- passages naming an artifact, commitments reach artifacts through their evidence
create table if not exists artifact_evidence
(
    artifact_id bigint not null references implementation_artifacts (id),
    evidence_id bigint not null references evidence (id),
    primary key (artifact_id, evidence_id)
);
create index if not exists artifact_evidence_evidence_idx on artifact_evidence (evidence_id);

-- osm streets/squares + parcel numbers (hrsz) seen in official docs
create table if not exists places
(
    id             bigint generated always as identity primary key,
    kind           text    not null check (kind in ('street', 'square', 'park', 'area', 'parcel')),
    name           text    not null,
    canonical_name text    not null,
    district       text    not null default '',
    osm_id         text,
    geojson        text,
    source         text    not null,
    confirmed      boolean not null default false,
    unique (kind, name, district)
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_api') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON implementation_artifacts, artifact_evidence, places
      TO paper_trail_api;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO paper_trail_api;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='paper_trail_worker') THEN
    GRANT SELECT ON implementation_artifacts, artifact_evidence, places TO paper_trail_worker;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO paper_trail_worker;
    GRANT INSERT (polarity, flags, procurement_ids, parcels),
      UPDATE (polarity, flags, procurement_ids, parcels) ON evidence TO paper_trail_worker;
    -- artifact status is an automatic warning, not a decision
    GRANT INSERT (procurement_id, status, status_evidence_id),
      UPDATE (status, status_evidence_id, updated_at) ON implementation_artifacts TO paper_trail_worker;
    GRANT INSERT ON artifact_evidence TO paper_trail_worker;
    -- workers record parcels they read, only a person confirms
    GRANT INSERT (kind, name, canonical_name, district, source) ON places TO paper_trail_worker;
  END IF;
END $$;
