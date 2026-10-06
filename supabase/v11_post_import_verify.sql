-- MingGui v1.1 biography post-import verification.
-- Run after all audited biography artifacts/chunks are imported, before coverage review/freeze.

-- Headline import state.
select
  ds.id::text snapshot_id,
  ds.version,
  ds.status,
  ds.observation_cutoff_date,
  (select count(*) from research.dataset_membership dm where dm.dataset_snapshot_id=ds.id)::int people,
  (select count(*) from research.person_snapshot_facts psf where psf.dataset_snapshot_id=ds.id)::int person_facts,
  (select count(*) from research.dataset_event_membership dem where dem.dataset_snapshot_id=ds.id)::bigint raw_event_memberships,
  (select count(*) from research.dataset_event_membership dem where dem.dataset_snapshot_id=ds.id and dem.snapshot_model_eligible)::bigint active_event_memberships,
  (select count(*) from research.artifact_import_authorizations a
   where a.importer_key='v11-biography-shard-v1'
     and a.target_snapshot_id=ds.id)::int biography_authorizations,
  (select count(*) from research.artifact_import_authorizations a
   where a.importer_key='v11-biography-shard-v1'
     and a.target_snapshot_id=ds.id
     and a.status='imported')::int biography_authorizations_imported
from research.dataset_snapshots ds
where ds.id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;

-- Every v1.0 person membership must still exist in v1.1.
select count(*)::int missing_parent_people
from research.dataset_membership p
left join research.dataset_membership c
  on c.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
 and c.person_id=p.person_id
where p.dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
  and c.person_id is null;

-- Every v1.0 raw event membership must still exist in v1.1.
-- Eligibility may differ snapshot-locally because old Wikipedia revisions can be superseded.
select count(*)::int missing_parent_event_memberships
from research.dataset_event_membership p
left join research.dataset_event_membership c
  on c.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
 and c.event_id=p.event_id
where p.dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
  and c.event_id is null;

-- Authorization/chunk manifest completeness.
with auth as (
  select
    provider_artifact_id,
    status,
    metadata,
    jsonb_object_length(coalesce(metadata->'import_chunks','{}'::jsonb)) expected_chunks
  from research.artifact_import_authorizations
  where importer_key='v11-biography-shard-v1'
    and provider='github-actions'
    and target_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
), actual as (
  select
    provider_artifact_id,
    count(*) filter(where status='imported')::int imported_chunks,
    count(distinct chunk_name)::int distinct_chunks
  from research.artifact_import_chunks
  where importer_key='v11-biography-shard-v1'
    and provider='github-actions'
  group by provider_artifact_id
)
select
  a.provider_artifact_id,
  a.status authorization_status,
  a.expected_chunks,
  coalesce(x.imported_chunks,0) imported_chunks,
  coalesce(x.distinct_chunks,0) distinct_chunks,
  a.metadata->>'storage_path' storage_path,
  (
    a.status='imported'
    and a.expected_chunks=coalesce(x.imported_chunks,0)
    and a.expected_chunks=coalesce(x.distinct_chunks,0)
    and nullif(a.metadata->>'storage_path','') is not null
  ) complete
from auth a
left join actual x using(provider_artifact_id)
order by (a.metadata->>'shard')::int;

-- Imported artifact registry must match the exact authorized artifacts.
select
  a.provider_artifact_id,
  a.sha256 authorization_sha,
  r.sha256 registry_sha,
  r.status registry_status,
  r.storage_path,
  jsonb_typeof(r.metadata) metadata_type,
  (
    r.sha256=a.sha256
    and r.status='imported'
    and r.storage_path=a.metadata->>'storage_path'
  ) exact_match
from research.artifact_import_authorizations a
left join research.artifact_registry r
  on r.provider='github-actions'
 and r.provider_artifact_id=a.provider_artifact_id
 and r.sha256=a.sha256
where a.importer_key='v11-biography-shard-v1'
  and a.target_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
order by (a.metadata->>'shard')::int;

-- Current-revision Wikipedia narrative layer: at most one active revision/person.
with active as (
  select
    e.person_id,
    e.attributes->>'revision_id' revision_id,
    count(*)::int events
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
  where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
    and dem.snapshot_model_eligible
    and e.source_family='wikipedia'
    and e.extraction_method='rule-from-revision-text'
  group by e.person_id,e.attributes->>'revision_id'
)
select count(*)::int people_with_multiple_active_wikipedia_revisions
from (
  select person_id
  from active
  group by person_id
  having count(*)>1
) x;

-- Superseded membership must be preserved but inactive.
select
  count(*)::int superseded_memberships,
  count(*) filter(where snapshot_model_eligible)::int superseded_still_active
from research.dataset_event_membership
where dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
  and exclusion_reason='superseded_by_v11_biography_revision';

-- Hard temporal eligibility gates.
select
  count(*) filter(
    where dem.snapshot_model_eligible
      and e.observable_from>'2026-10-06'::date
  )::int active_after_cutoff,
  count(*) filter(
    where dem.snapshot_model_eligible
      and e.event_date_min>'2026-10-06'::date
  )::int active_start_after_cutoff,
  count(*) filter(
    where dem.snapshot_model_eligible
      and e.age_max<0
  )::int active_prebirth,
  count(*) filter(
    where dem.snapshot_model_eligible
      and (e.event_date_min is null or e.event_date_max is null or e.observable_from is null)
  )::int active_missing_temporal_bounds
from research.dataset_event_membership dem
join research.life_events e on e.id=dem.event_id
where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;

-- Every v1.1 biography candidate must remain source-backed.
select
  count(*)::int v11_candidates,
  count(*) filter(where source_record_id is null)::int candidates_missing_source,
  count(distinct person_id)::int candidate_people
from research.event_candidates
where metadata ? 'v11_artifact_id';

-- Every v1.1 Wikipedia rule event must have evidence, a revision source, and snapshot membership.
with v11_events as (
  select e.*
  from research.life_events e
  where e.source_family='wikipedia'
    and e.extraction_method='rule-from-revision-text'
    and e.attributes ? 'v11_artifact_id'
)
select
  count(*)::int v11_rule_events,
  count(*) filter(where not exists(
    select 1 from research.event_evidence ee where ee.event_id=e.id
  ))::int events_missing_evidence,
  count(*) filter(where not exists(
    select 1
    from research.event_evidence ee
    join research.source_records sr on sr.id=ee.source_record_id
    where ee.event_id=e.id
      and sr.source_family='wikipedia'
      and sr.revision_id=e.attributes->>'revision_id'
  ))::int events_missing_matching_revision_source,
  count(*) filter(where not exists(
    select 1 from research.dataset_event_membership dem
    where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
      and dem.event_id=e.id
  ))::int events_missing_v11_membership
from v11_events e;

-- Zero-event coverage delta: primary enrichment success metric.
with counts as (
  select
    dm.dataset_snapshot_id,
    dm.person_id,
    count(dem.event_id) filter(where dem.snapshot_model_eligible)::int n
  from research.dataset_membership dm
  left join research.life_events e on e.person_id=dm.person_id
  left join research.dataset_event_membership dem
    on dem.dataset_snapshot_id=dm.dataset_snapshot_id
   and dem.event_id=e.id
  where dm.dataset_snapshot_id in (
    '42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid,
    '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
  )
  group by dm.dataset_snapshot_id,dm.person_id
)
select
  dataset_snapshot_id::text,
  count(*)::int people,
  count(*) filter(where n=0)::int zero_event_people,
  count(*) filter(where n=1)::int one_event_people,
  round(avg(n)::numeric,3) mean_active_events,
  percentile_cont(0.5) within group(order by n) median_active_events,
  percentile_cont(0.9) within group(order by n) p90_active_events
from counts
group by dataset_snapshot_id
order by dataset_snapshot_id;
