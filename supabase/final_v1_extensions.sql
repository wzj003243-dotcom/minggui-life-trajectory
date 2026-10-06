-- MingGui final v1 reproducibility extensions
-- Apply after supabase/lifegraph_v2.sql and supabase/training_v1.sql.
-- This file captures the schema objects added while freezing the final v1 training corpus.
-- Dataset-specific rows/fingerprints remain data and are documented in research/training/TRAINING_DATA_CONTRACT.md.

create schema if not exists research;
revoke all on schema research from public,anon,authenticated;
grant usage on schema research to service_role;

-- Snapshot-level reproducibility fields.
alter table research.dataset_snapshots
  add column if not exists model_event_count bigint,
  add column if not exists observation_cutoff_date date,
  add column if not exists frozen_at timestamptz,
  add column if not exists person_membership_sha256 text,
  add column if not exists event_membership_sha256 text,
  add column if not exists canonical_event_count bigint,
  add column if not exists canonical_event_sha256 text,
  add column if not exists canonicalization_version text;

alter table research.dataset_event_membership
  add column if not exists snapshot_model_eligible boolean not null default true,
  add column if not exists exclusion_reason text;

alter table research.feature_snapshots
  add column if not exists included_canonical_event_keys text[] not null default '{}',
  add column if not exists canonicalization_version text;

-- Freeze mutable person facts into each dataset snapshot.
create table if not exists research.person_snapshot_facts (
  dataset_snapshot_id uuid not null references research.dataset_snapshots(id) on delete cascade,
  person_id bigint not null references research.people(id) on delete cascade,
  canonical_name text,
  gender text,
  birth_date date,
  birth_time time,
  birth_time_known boolean not null default false,
  birth_place text,
  birth_country text,
  birth_country_normalized text,
  birth_geo_group text,
  latitude double precision,
  longitude double precision,
  birth_reliability text,
  death_date date,
  death_year integer,
  source_birth_record_id bigint references research.birth_records(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key(dataset_snapshot_id,person_id)
);
create index if not exists person_snapshot_facts_source_birth_record_idx
  on research.person_snapshot_facts(source_birth_record_id);

-- Durable registry for raw artifacts copied out of temporary GitHub Actions storage.
create table if not exists research.artifact_registry (
  id uuid primary key default gen_random_uuid(),
  artifact_key text not null unique,
  provider text not null,
  provider_artifact_id text,
  artifact_name text not null,
  artifact_kind text not null,
  sha256 text not null,
  size_bytes bigint,
  source_workflow_run_id text,
  source_git_sha text,
  storage_bucket text,
  storage_path text,
  status text not null default 'registered',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  archived_at timestamptz,
  imported_at timestamptz,
  unique(provider,provider_artifact_id,sha256)
);
create index if not exists artifact_registry_kind_status_idx
  on research.artifact_registry(artifact_kind,status);
create index if not exists artifact_registry_sha_idx
  on research.artifact_registry(sha256);

-- Present-day geography is stored as a separate control, not rewritten as historical nationality.
create table if not exists research.geography_feature_sets (
  dataset_snapshot_id uuid not null references research.dataset_snapshots(id) on delete cascade,
  person_id bigint not null references research.people(id) on delete cascade,
  feature_version text not null,
  birthplace_qid text,
  birthplace_label_en text,
  p19_rank text,
  p19_candidate_count integer,
  wikidata_latitude double precision,
  wikidata_longitude double precision,
  present_day_country_qid text,
  present_day_country_label_en text,
  country_resolution text,
  admin_parent_qids text[] not null default '{}',
  timezone_qids text[] not null default '{}',
  astro_place text,
  astro_country_raw text,
  astro_latitude double precision,
  astro_longitude double precision,
  coordinate_delta_km double precision,
  geo_primary_eligible boolean not null default false,
  country_semantics text,
  source_artifact_id text,
  raw_features jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key(dataset_snapshot_id,person_id,feature_version)
);
create index if not exists geography_feature_sets_person_idx
  on research.geography_feature_sets(person_id);
create index if not exists geography_feature_sets_country_idx
  on research.geography_feature_sets(dataset_snapshot_id,present_day_country_qid);
create index if not exists geography_feature_sets_eligible_idx
  on research.geography_feature_sets(dataset_snapshot_id,geo_primary_eligible);

create or replace view research.snapshot_geography_coverage_v1
with (security_invoker=true) as
select
  ds.id as dataset_snapshot_id,ds.version,
  count(dm.person_id)::int as cohort_people,
  count(g.person_id)::int as geography_rows,
  count(g.person_id) filter(where g.geo_primary_eligible)::int as geo_primary_eligible,
  count(g.person_id) filter(where g.present_day_country_qid is not null)::int as country_resolved,
  (count(dm.person_id)-count(g.person_id))::int as missing_geography_rows
from research.dataset_snapshots ds
join research.dataset_membership dm on dm.dataset_snapshot_id=ds.id
left join research.geography_feature_sets g
  on g.dataset_snapshot_id=ds.id
 and g.person_id=dm.person_id
 and g.feature_version='present-day-wikidata-geo-v1'
group by ds.id,ds.version;

-- Conservative canonicalization: only exact subject-backed duplicates merge.
create or replace view research.snapshot_canonical_events_v1
with (security_invoker=true) as
with keyed as (
  select
    dem.dataset_snapshot_id,
    e.id as raw_event_id,
    e.event_key as raw_event_key,
    e.person_id,e.domain,e.event_type,e.event_date_min,e.event_date_max,
    e.temporal_precision,e.calendar_kind,e.age_min,e.age_max,e.age_mid,
    e.observable_from,e.subject_external_id,e.source_family,e.confidence,
    e.source_rank,e.qualifier_kind,e.model_eligible,e.quality_flags,
    dem.snapshot_model_eligible,dem.exclusion_reason,
    case
      when e.subject_external_id is not null and btrim(e.subject_external_id)<>'' then
        'ce:v1:'||encode(extensions.digest(
          concat_ws(E'\x1f',
            e.person_id::text,e.domain,e.event_type,
            coalesce(e.event_date_min::text,''),
            coalesce(e.event_date_max::text,''),
            coalesce(e.qualifier_kind,''),
            e.subject_external_id
          ),'sha256'),'hex')
      else
        'ce:v1:raw:'||encode(extensions.digest(e.event_key,'sha256'),'hex')
    end as canonical_event_key
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
)
select
  dataset_snapshot_id,canonical_event_key,person_id,domain,event_type,
  min(event_date_min) as event_date_min,
  max(event_date_max) as event_date_max,
  case when count(distinct temporal_precision)=1 then min(temporal_precision) else 'mixed' end as temporal_precision,
  case when count(distinct calendar_kind)=1 then min(calendar_kind) else null end as calendar_kind,
  min(age_min) as age_min,
  max(age_max) as age_max,
  avg(age_mid) filter(where age_mid is not null) as age_mid,
  max(observable_from) as observable_from,
  max(subject_external_id) as subject_external_id,
  max(confidence) as confidence_max,
  bool_or(snapshot_model_eligible) as snapshot_model_eligible,
  array_agg(distinct source_family order by source_family) as source_families,
  count(distinct source_family)::int as source_family_count,
  count(*)::int as raw_event_count,
  array_agg(raw_event_key order by raw_event_key) as raw_event_keys,
  array_agg(raw_event_id order by raw_event_id) as raw_event_ids,
  jsonb_build_object(
    'canonicalization_version','exact-subject-v1',
    'merge_policy','subject-backed exact type/date/qualifier; subjectless events remain distinct',
    'quality_flags',jsonb_agg(quality_flags order by raw_event_key),
    'exclusion_reasons',jsonb_agg(exclusion_reason order by raw_event_key)
  ) as canonicalization_metadata
from keyed
group by dataset_snapshot_id,canonical_event_key,person_id,domain,event_type;

-- Materialized canonical facts are the immutable training source for a frozen snapshot.
create table if not exists research.snapshot_canonical_event_facts (
  dataset_snapshot_id uuid not null references research.dataset_snapshots(id) on delete cascade,
  canonical_event_key text not null,
  person_id bigint not null references research.people(id) on delete cascade,
  domain text not null,
  event_type text not null,
  event_date_min date,
  event_date_max date,
  temporal_precision text,
  calendar_kind text,
  age_min double precision,
  age_max double precision,
  age_mid double precision,
  observable_from date,
  subject_external_id text,
  confidence_max double precision,
  snapshot_model_eligible boolean not null,
  source_families text[] not null default '{}',
  source_family_count integer not null default 0,
  raw_event_count integer not null default 0,
  raw_event_keys text[] not null default '{}',
  raw_event_ids bigint[] not null default '{}',
  canonicalization_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key(dataset_snapshot_id,canonical_event_key)
);
create index if not exists snapshot_canonical_event_person_obs_idx
  on research.snapshot_canonical_event_facts(dataset_snapshot_id,person_id,observable_from)
  where snapshot_model_eligible and observable_from is not null;
create index if not exists snapshot_canonical_event_person_domain_idx
  on research.snapshot_canonical_event_facts(dataset_snapshot_id,person_id,domain)
  where snapshot_model_eligible;
create index if not exists snapshot_canonical_event_facts_person_idx
  on research.snapshot_canonical_event_facts(person_id);

create or replace view research.snapshot_canonicalization_report_v1
with (security_invoker=true) as
with raw_counts as (
  select dataset_snapshot_id,count(*)::bigint raw_event_memberships
  from research.dataset_event_membership
  group by dataset_snapshot_id
),
canon_counts as (
  select dataset_snapshot_id,
         count(*)::bigint canonical_events,
         count(*) filter(where raw_event_count>1)::bigint multi_raw_canonical_events,
         count(*) filter(where source_family_count>1)::bigint multi_source_canonical_events
  from research.snapshot_canonical_events_v1
  group by dataset_snapshot_id
)
select
  ds.id as dataset_snapshot_id,ds.version,
  coalesce(r.raw_event_memberships,0)::bigint as raw_event_memberships,
  coalesce(c.canonical_events,0)::bigint as canonical_events,
  (coalesce(r.raw_event_memberships,0)-coalesce(c.canonical_events,0))::bigint as exact_duplicate_memberships_collapsed,
  coalesce(c.multi_raw_canonical_events,0)::bigint as multi_raw_canonical_events,
  coalesce(c.multi_source_canonical_events,0)::bigint as multi_source_canonical_events
from research.dataset_snapshots ds
left join raw_counts r on r.dataset_snapshot_id=ds.id
left join canon_counts c on c.dataset_snapshot_id=ds.id
where ds.dataset_key='timed-core';

-- Training-table additions.
alter table research.training_examples
  add column if not exists history_raw_event_count integer not null default 0,
  add column if not exists target_canonical_event_key text,
  add column if not exists canonicalization_version text;
create index if not exists training_examples_target_canonical_idx
  on research.training_examples(target_canonical_event_key);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='training_examples_history_raw_count_nonnegative'
      and conrelid='research.training_examples'::regclass
  ) then
    alter table research.training_examples
      add constraint training_examples_history_raw_count_nonnegative
      check(history_raw_event_count>=0);
  end if;
end $$;

-- Fixed staging table avoids repeated dynamic trajectory reconstruction during training materialization.
create table if not exists research.training_cutoff_materializations (
  dataset_snapshot_id uuid not null,
  person_id bigint not null,
  wikidata_id text,
  cutoff_age integer not null,
  cutoff_date date,
  information_cutoff date,
  history_event_count integer,
  history_raw_event_count integer,
  history_domain_count integer,
  history_source_family_count integer,
  history_life_stage_count integer,
  history_summary jsonb,
  included_event_keys text[],
  included_canonical_event_keys text[],
  target_event_key text,
  target_canonical_event_key text,
  target_domain text,
  target_event_type text,
  target_observable_from date,
  target_age double precision,
  target_payload jsonb,
  observation_end_date date,
  right_censored boolean,
  censoring_reason text,
  observation_profile jsonb,
  eligibility_flags jsonb,
  candidate_spec_version text not null,
  materialized_at timestamptz not null,
  primary key(dataset_snapshot_id,person_id,cutoff_age,candidate_spec_version)
);
create index if not exists training_cutoff_materializations_snapshot_idx
  on research.training_cutoff_materializations(dataset_snapshot_id,candidate_spec_version);
create index if not exists training_cutoff_materializations_target_idx
  on research.training_cutoff_materializations(dataset_snapshot_id,target_canonical_event_key);

-- Frozen placebo donor maps.
create table if not exists research.training_placebo_person_map (
  training_dataset_id uuid not null references research.training_dataset_versions(id) on delete cascade,
  scenario_key text not null references research.training_split_scenarios(scenario_key),
  person_id bigint not null references research.people(id) on delete cascade,
  donor_person_id bigint references research.people(id) on delete restrict,
  split_name text not null,
  birth_decade integer not null,
  eligible boolean not null,
  ineligible_reason text,
  seed text not null,
  assignment_hash text,
  created_at timestamptz not null default now(),
  primary key(training_dataset_id,scenario_key,person_id),
  constraint placebo_no_self_donor check(donor_person_id is null or donor_person_id<>person_id),
  constraint placebo_eligible_has_donor check((eligible and donor_person_id is not null) or (not eligible))
);
create index if not exists training_placebo_map_donor_idx
  on research.training_placebo_person_map(training_dataset_id,scenario_key,donor_person_id);
create index if not exists training_placebo_person_map_donor_person_idx
  on research.training_placebo_person_map(donor_person_id);
create index if not exists training_placebo_person_map_person_idx
  on research.training_placebo_person_map(person_id);
create index if not exists training_placebo_person_map_scenario_idx
  on research.training_placebo_person_map(scenario_key);

-- Frozen benchmark protocol.
create table if not exists research.training_benchmark_protocols (
  protocol_key text primary key,
  protocol_version text not null,
  training_dataset_id uuid not null references research.training_dataset_versions(id) on delete restrict,
  task_key text not null references research.training_task_definitions(task_key),
  primary_target text not null,
  eligibility_policy jsonb not null,
  feature_variants text[] not null,
  split_scenarios text[] not null,
  metrics jsonb not null,
  weighting_policy jsonb not null,
  model_policy jsonb not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists training_benchmark_protocols_task_idx
  on research.training_benchmark_protocols(task_key);
create index if not exists training_benchmark_protocols_dataset_idx
  on research.training_benchmark_protocols(training_dataset_id);

-- Private-schema access control.
alter table research.person_snapshot_facts enable row level security;
alter table research.artifact_registry enable row level security;
alter table research.geography_feature_sets enable row level security;
alter table research.snapshot_canonical_event_facts enable row level security;
alter table research.training_cutoff_materializations enable row level security;
alter table research.training_placebo_person_map enable row level security;
alter table research.training_benchmark_protocols enable row level security;

do $$
declare t text;
begin
  foreach t in array array[
    'person_snapshot_facts','artifact_registry','geography_feature_sets',
    'snapshot_canonical_event_facts','training_cutoff_materializations',
    'training_placebo_person_map','training_benchmark_protocols'
  ]
  loop
    execute format('drop policy if exists %I on research.%I','service_role_all_'||t,t);
    execute format(
      'create policy %I on research.%I for all to service_role using (true) with check (true)',
      'service_role_all_'||t,t
    );
    execute format('revoke all on research.%I from public,anon,authenticated',t);
    execute format('grant select,insert,update,delete on research.%I to service_role',t);
  end loop;
end $$;

grant select on research.snapshot_geography_coverage_v1,
                research.snapshot_canonical_events_v1,
                research.snapshot_canonicalization_report_v1
to service_role;

-- The production database also contains:
--   research.training_cutoff_candidates_strict_v1
--   research.training_cutoff_candidates_legacy_replay_v1
--   research.training_cutoff_policy_diff_v1
--   research.training_cutoff_candidates_canonical_v1
-- and research.freeze_dataset_snapshot_v1(uuid,date) at freeze_spec_version snapshot-freeze-v3.
-- Their exact frozen semantics are specified in TRAINING_DATA_CONTRACT.md and verified by the v1.0 fingerprints.
