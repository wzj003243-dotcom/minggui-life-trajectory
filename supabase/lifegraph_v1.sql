-- LifeGraph v1 research storage.
-- Research schema stays server-side only; never grant direct client access.

create schema if not exists research;

alter table research.life_events
  add column if not exists event_key text,
  add column if not exists event_date_min date,
  add column if not exists event_date_max date,
  add column if not exists temporal_precision text,
  add column if not exists age_min double precision,
  add column if not exists age_max double precision,
  add column if not exists observable_from date,
  add column if not exists subject_external_id text,
  add column if not exists extraction_method text;

create unique index if not exists life_events_event_key_uidx
  on research.life_events(event_key) where event_key is not null;
create index if not exists life_events_person_age_idx
  on research.life_events(person_id, age_years);
create index if not exists life_events_person_date_idx
  on research.life_events(person_id, event_date_min);
create index if not exists life_events_type_idx
  on research.life_events(event_type);

create table if not exists research.source_records (
  id bigserial primary key,
  source_key text not null unique,
  source_type text not null,
  publisher text,
  title text,
  url text,
  dataset_version text,
  revision_id text,
  retrieved_at timestamptz not null default now(),
  license_bucket text not null,
  license_url text,
  content_hash text,
  independence_group text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists research.event_evidence (
  id bigserial primary key,
  event_id bigint not null references research.life_events(id) on delete cascade,
  source_record_id bigint not null references research.source_records(id) on delete restrict,
  evidence_text text,
  evidence_locator text,
  extractor_version text,
  confidence double precision check (confidence between 0 and 1),
  metadata jsonb not null default '{}'::jsonb,
  unique(event_id, source_record_id, evidence_locator)
);

create table if not exists research.external_identities (
  id bigserial primary key,
  person_id bigint not null references research.people(id) on delete cascade,
  source text not null,
  external_id text not null,
  status text not null,
  verification_method text,
  verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique(source, external_id),
  unique(person_id, source)
);

create table if not exists research.person_year_states (
  id bigserial primary key,
  person_id bigint not null references research.people(id) on delete cascade,
  year integer not null check (year between -5000 and 3000),
  state_spec_version text not null,
  information_cutoff date not null,
  state jsonb not null,
  source_snapshot_id text,
  created_at timestamptz not null default now(),
  unique(person_id, year, state_spec_version)
);

create index if not exists person_year_states_person_year_idx
  on research.person_year_states(person_id, year);

create table if not exists research.feature_snapshots (
  id bigserial primary key,
  person_id bigint not null references research.people(id) on delete cascade,
  information_cutoff date not null,
  feature_spec_version text not null,
  features jsonb not null,
  included_event_keys text[] not null default '{}',
  leakage_audit_passed boolean not null default false,
  source_snapshot_id text,
  created_at timestamptz not null default now(),
  unique(person_id, information_cutoff, feature_spec_version)
);

revoke all on all tables in schema research from anon, authenticated;
