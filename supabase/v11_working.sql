-- MingGui v1.1 working snapshot: copy-on-write lineage and import authorization.

-- This file records the live v1.1 working snapshot. Frozen v1.0 is never mutated.
insert into research.dataset_snapshots(
  id,dataset_key,version,status,person_count,event_count,model_event_count,observation_cutoff_date,metadata
)
values(
  '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid,
  'timed-core','v1.1-working','draft',3398,31710,31512,date '2026-10-06',
  '{
    "parent_snapshot_id":"42628250-3a51-4b92-b4bd-12c7dec846a8",
    "parent_version":"v1.0-final-identity",
    "lineage_policy":"copy-on-write",
    "baseline_person_count":3398,
    "baseline_raw_event_memberships":31710,
    "baseline_model_eligible_raw_events":31512,
    "baseline_canonical_events":31655,
    "baseline_person_membership_sha256":"ddf9631abaa04cfa89ce0810d3ba1b4fa2ca6bb6cfa033bbfc81c6a74f8e05da",
    "baseline_event_membership_sha256":"be680992ce8b188f107cfac31f9c384311071701c032ca73722fe51de9712003",
    "baseline_canonical_sha256":"88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654",
    "purpose":"v1.1 enrichment branch; never mutate frozen v1.0",
    "planned_observation_cutoff_date":"2026-10-06",
    "cutoff_semantics":"events observable after 2026-10-06 remain preserved but snapshot-model-ineligible",
    "freeze_policy":"recompute counts, canonical facts, memberships, and fingerprints before v1.1 freeze"
  }'::jsonb
)
on conflict(dataset_key,version) do update set
  status='draft',
  observation_cutoff_date=excluded.observation_cutoff_date,
  metadata=research.dataset_snapshots.metadata||excluded.metadata;

insert into research.dataset_membership(dataset_snapshot_id,person_id,cohort_role,metadata)
select
  '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid,
  person_id,cohort_role,
  coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'inherited_from_snapshot','42628250-3a51-4b92-b4bd-12c7dec846a8',
    'inheritance_mode','baseline-copy'
  )
from research.dataset_membership
where dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
on conflict(dataset_snapshot_id,person_id) do nothing;

insert into research.dataset_event_membership(
  dataset_snapshot_id,event_id,inclusion_role,metadata,
  snapshot_model_eligible,exclusion_reason
)
select
  '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid,
  event_id,inclusion_role,
  coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'inherited_from_snapshot','42628250-3a51-4b92-b4bd-12c7dec846a8',
    'inheritance_mode','baseline-copy'
  ),
  snapshot_model_eligible,exclusion_reason
from research.dataset_event_membership
where dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
on conflict(dataset_snapshot_id,event_id) do nothing;

insert into research.person_snapshot_facts(
  dataset_snapshot_id,person_id,canonical_name,gender,birth_date,birth_time,birth_time_known,
  birth_place,birth_country,birth_country_normalized,birth_geo_group,latitude,longitude,
  birth_reliability,death_date,death_year,source_birth_record_id,metadata
)
select
  '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid,
  person_id,canonical_name,gender,birth_date,birth_time,birth_time_known,
  birth_place,birth_country,birth_country_normalized,birth_geo_group,latitude,longitude,
  birth_reliability,death_date,death_year,source_birth_record_id,
  coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
    'inherited_from_snapshot','42628250-3a51-4b92-b4bd-12c7dec846a8',
    'inheritance_mode','baseline-copy'
  )
from research.person_snapshot_facts
where dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
on conflict(dataset_snapshot_id,person_id) do nothing;

create table if not exists research.artifact_import_authorizations (
  importer_key text not null,
  provider text not null,
  provider_artifact_id text not null,
  sha256 text not null,
  target_snapshot_id uuid not null references research.dataset_snapshots(id) on delete restrict,
  status text not null default 'approved'
    check(status in ('approved','imported','revoked','superseded')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  imported_at timestamptz,
  primary key(importer_key,provider,provider_artifact_id),
  unique(importer_key,sha256)
);

create index if not exists artifact_import_auth_target_snapshot_idx
  on research.artifact_import_authorizations(target_snapshot_id);

alter table research.artifact_import_authorizations enable row level security;
drop policy if exists service_role_all_artifact_import_authorizations
  on research.artifact_import_authorizations;
create policy service_role_all_artifact_import_authorizations
on research.artifact_import_authorizations for all to service_role
using(true) with check(true);

revoke all on research.artifact_import_authorizations from public,anon,authenticated;
grant select,insert,update,delete on research.artifact_import_authorizations to service_role;
