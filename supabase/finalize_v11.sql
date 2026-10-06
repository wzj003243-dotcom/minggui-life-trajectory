-- MingGui v1.1 freeze finalizer.
-- DO NOT run until all v1.1 biography shards are imported and union audit passes.
--
-- Freeze/hash spec: snapshot-freeze-v4
--   person_membership_sha256:
--     sha256 of newline-delimited sorted Wikidata QIDs.
--   event_membership_sha256:
--     sha256 of newline-delimited JSONB records ordered by event_key containing
--     event_key, snapshot_model_eligible, exclusion_reason.
--   canonical_event_sha256:
--     sha256 of newline-delimited JSONB canonical fact records ordered by
--     canonical_event_key. The serialization explicitly includes raw provenance.
--
-- JSONB text output is used intentionally because PostgreSQL emits JSONB object
-- keys deterministically; arrays are constructed in explicit order.

do $$
declare
  v_snapshot constant uuid := '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02';
  v_parent constant uuid := '42628250-3a51-4b92-b4bd-12c7dec846a8';
  v_cutoff constant date := date '2026-10-06';

  v_status text;
  v_people integer;
  v_facts integer;
  v_events integer;
  v_eligible integer;
  v_bad_future integer;
  v_bad_prebirth integer;
  v_multi_active_wiki_revision_people integer;
  v_bad_supersession integer;
  v_pending_auth integer;
  v_parent_people_hash text;
  v_parent_event_hash text;
  v_parent_canonical_hash text;
begin
  select status into v_status
  from research.dataset_snapshots
  where id=v_snapshot;

  if v_status is distinct from 'draft' then
    raise exception 'v1.1 snapshot must be draft before finalization; status=%',v_status;
  end if;

  select count(*)::int into v_people
  from research.dataset_membership
  where dataset_snapshot_id=v_snapshot;

  if v_people<>3398 then
    raise exception 'v1.1 person membership mismatch: % != 3398',v_people;
  end if;

  select count(*)::int into v_facts
  from research.person_snapshot_facts
  where dataset_snapshot_id=v_snapshot;

  if v_facts<>3398 then
    raise exception 'v1.1 person snapshot facts mismatch: % != 3398',v_facts;
  end if;

  select
    person_membership_sha256,
    event_membership_sha256,
    canonical_event_sha256
  into
    v_parent_people_hash,
    v_parent_event_hash,
    v_parent_canonical_hash
  from research.dataset_snapshots
  where id=v_parent;

  if v_parent_people_hash is distinct from 'ddf9631abaa04cfa89ce0810d3ba1b4fa2ca6bb6cfa033bbfc81c6a74f8e05da'
     or v_parent_event_hash is distinct from 'be680992ce8b188f107cfac31f9c384311071701c032ca73722fe51de9712003'
     or v_parent_canonical_hash is distinct from '88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654'
  then
    raise exception 'frozen v1.0 parent fingerprints changed';
  end if;

  select count(*)::int into v_bad_future
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
  where dem.dataset_snapshot_id=v_snapshot
    and dem.snapshot_model_eligible
    and (
      (e.observable_from is not null and e.observable_from>v_cutoff)
      or (e.event_date_min is not null and e.event_date_min>v_cutoff)
    );

  if v_bad_future<>0 then
    raise exception 'v1.1 has % active events beyond observation cutoff',v_bad_future;
  end if;

  select count(*)::int into v_bad_prebirth
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
  where dem.dataset_snapshot_id=v_snapshot
    and dem.snapshot_model_eligible
    and e.age_max<0;

  if v_bad_prebirth<>0 then
    raise exception 'v1.1 has % active pre-birth events',v_bad_prebirth;
  end if;

  -- A person may retain every historical Wikipedia revision in raw storage, but
  -- only one revision of narrative-rule events may be active in this snapshot.
  with active_revision as (
    select
      e.person_id,
      coalesce(e.attributes->>'revision_id','') revision_id
    from research.dataset_event_membership dem
    join research.life_events e on e.id=dem.event_id
    where dem.dataset_snapshot_id=v_snapshot
      and dem.snapshot_model_eligible
      and e.source_family='wikipedia'
      and coalesce(e.extraction_method,'')='rule-from-revision-text'
    group by e.person_id,coalesce(e.attributes->>'revision_id','')
  )
  select count(*)::int into v_multi_active_wiki_revision_people
  from (
    select person_id
    from active_revision
    group by person_id
    having count(*)>1
  ) x;

  if v_multi_active_wiki_revision_people<>0 then
    raise exception 'v1.1 has % people with multiple active Wikipedia narrative revisions',
      v_multi_active_wiki_revision_people;
  end if;

  -- Anything explicitly marked superseded must never still be active.
  select count(*)::int into v_bad_supersession
  from research.dataset_event_membership
  where dataset_snapshot_id=v_snapshot
    and exclusion_reason='superseded_by_v11_biography_revision'
    and snapshot_model_eligible;

  if v_bad_supersession<>0 then
    raise exception 'v1.1 has % superseded events still marked active',v_bad_supersession;
  end if;

  select count(*)::int into v_pending_auth
  from research.artifact_import_authorizations
  where importer_key='v11-biography-shard-v1'
    and target_snapshot_id=v_snapshot
    and status<>'imported';

  if v_pending_auth<>0 then
    raise exception 'v1.1 has % biography artifact authorizations not imported',v_pending_auth;
  end if;

  -- Rebuild canonical facts from the snapshot-specific membership.
  delete from research.snapshot_canonical_event_facts
  where dataset_snapshot_id=v_snapshot;

  insert into research.snapshot_canonical_event_facts(
    dataset_snapshot_id,canonical_event_key,person_id,domain,event_type,
    event_date_min,event_date_max,temporal_precision,calendar_kind,
    age_min,age_max,age_mid,observable_from,subject_external_id,
    confidence_max,snapshot_model_eligible,source_families,source_family_count,
    raw_event_count,raw_event_keys,raw_event_ids,canonicalization_metadata
  )
  select
    dataset_snapshot_id,canonical_event_key,person_id,domain,event_type,
    event_date_min,event_date_max,temporal_precision,calendar_kind,
    age_min,age_max,age_mid,observable_from,subject_external_id,
    confidence_max,snapshot_model_eligible,source_families,source_family_count,
    raw_event_count,raw_event_keys,raw_event_ids,canonicalization_metadata
  from research.snapshot_canonical_events_v1
  where dataset_snapshot_id=v_snapshot;

  select count(*)::int into v_events
  from research.dataset_event_membership
  where dataset_snapshot_id=v_snapshot;

  select count(*)::int into v_eligible
  from research.dataset_event_membership
  where dataset_snapshot_id=v_snapshot
    and snapshot_model_eligible;

  update research.dataset_snapshots
  set
    observation_cutoff_date=v_cutoff,
    person_count=v_people,
    event_count=v_events,
    model_event_count=v_eligible,
    canonical_event_count=(
      select count(*)::int
      from research.snapshot_canonical_event_facts
      where dataset_snapshot_id=v_snapshot
    ),
    canonicalization_version='exact-subject-v1',
    metadata=metadata||jsonb_build_object(
      'freeze_spec','snapshot-freeze-v4',
      'canonicalization_version','exact-subject-v1',
      'observation_cutoff_date',v_cutoff::text,
      'finalizer','supabase/finalize_v11.sql'
    )
  where id=v_snapshot;
end $$;

-- Compute stable v4 fingerprints in separate statements after canonical materialization.
with payload as (
  select string_agg(p.wikidata_id,E'\n' order by p.wikidata_id) s
  from research.dataset_membership dm
  join research.people p on p.id=dm.person_id
  where dm.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
)
update research.dataset_snapshots
set person_membership_sha256=encode(extensions.digest(coalesce(payload.s,''),'sha256'),'hex')
from payload
where id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;

with payload as (
  select string_agg(
    jsonb_build_object(
      'event_key',e.event_key,
      'snapshot_model_eligible',dem.snapshot_model_eligible,
      'exclusion_reason',dem.exclusion_reason
    )::text,
    E'\n'
    order by e.event_key
  ) s
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
  where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
)
update research.dataset_snapshots
set event_membership_sha256=encode(extensions.digest(coalesce(payload.s,''),'sha256'),'hex')
from payload
where id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;

with payload as (
  select string_agg(
    jsonb_build_object(
      'canonical_event_key',c.canonical_event_key,
      'wikidata_id',p.wikidata_id,
      'domain',c.domain,
      'event_type',c.event_type,
      'event_date_min',c.event_date_min,
      'event_date_max',c.event_date_max,
      'temporal_precision',c.temporal_precision,
      'observable_from',c.observable_from,
      'subject_external_id',c.subject_external_id,
      'snapshot_model_eligible',c.snapshot_model_eligible,
      'source_families',c.source_families,
      'raw_event_keys',c.raw_event_keys
    )::text,
    E'\n'
    order by c.canonical_event_key
  ) s
  from research.snapshot_canonical_event_facts c
  join research.people p on p.id=c.person_id
  where c.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
)
update research.dataset_snapshots
set canonical_event_sha256=encode(extensions.digest(coalesce(payload.s,''),'sha256'),'hex')
from payload
where id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;

-- Final safety gate before setting frozen.
do $$
declare
  v_snapshot constant uuid := '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02';
  v_people integer;
  v_events integer;
  v_eligible integer;
  v_canonical integer;
  v_ph text;
  v_eh text;
  v_ch text;
begin
  select
    person_count,event_count,model_event_count,canonical_event_count,
    person_membership_sha256,event_membership_sha256,canonical_event_sha256
  into v_people,v_events,v_eligible,v_canonical,v_ph,v_eh,v_ch
  from research.dataset_snapshots
  where id=v_snapshot;

  if v_people<>3398 then
    raise exception 'final person_count mismatch';
  end if;
  if v_events<31710 then
    raise exception 'v1.1 lost raw event membership: %',v_events;
  end if;
  if v_eligible<=0 or v_canonical<=0 then
    raise exception 'invalid final event/canonical counts';
  end if;
  if v_ph is null or length(v_ph)<>64
     or v_eh is null or length(v_eh)<>64
     or v_ch is null or length(v_ch)<>64
  then
    raise exception 'missing/invalid snapshot fingerprints';
  end if;

  update research.dataset_snapshots
  set
    status='frozen',
    frozen_at=now(),
    metadata=metadata||jsonb_build_object(
      'frozen_at',now()::text,
      'freeze_gate_passed',true
    )
  where id=v_snapshot and status='draft';
end $$;

select
  id::text,dataset_key,version,status,observation_cutoff_date,
  person_count,event_count,model_event_count,canonical_event_count,
  person_membership_sha256,event_membership_sha256,canonical_event_sha256,
  canonicalization_version,frozen_at,metadata
from research.dataset_snapshots
where id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid;
