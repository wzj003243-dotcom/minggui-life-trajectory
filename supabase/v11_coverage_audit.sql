-- MingGui v1.1 coverage/quality audit.
-- Read-only report queries to run after enrichment import and before freeze.

-- 1) Snapshot headline counts.
select
  ds.id::text snapshot_id,
  ds.version,
  ds.status,
  ds.observation_cutoff_date,
  count(distinct dm.person_id)::int people,
  count(distinct dem.event_id)::int raw_event_memberships,
  count(distinct dem.event_id) filter(where dem.snapshot_model_eligible)::int model_eligible_event_memberships,
  count(distinct dem.event_id) filter(where not dem.snapshot_model_eligible)::int retained_but_ineligible_event_memberships
from research.dataset_snapshots ds
join research.dataset_membership dm on dm.dataset_snapshot_id=ds.id
left join research.dataset_event_membership dem on dem.dataset_snapshot_id=ds.id
where ds.id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
group by ds.id;

-- 2) Per-person active event coverage distribution.
with per_person as (
  select
    dm.person_id,
    count(dem.event_id) filter(where dem.snapshot_model_eligible)::int eligible_events,
    count(dem.event_id)::int all_events
  from research.dataset_membership dm
  left join research.dataset_event_membership dem
    on dem.dataset_snapshot_id=dm.dataset_snapshot_id
   and dem.event_id in (
     select id from research.life_events e where e.person_id=dm.person_id
   )
  where dm.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
  group by dm.person_id
)
select
  count(*)::int people,
  count(*) filter(where eligible_events=0)::int zero_eligible_events,
  count(*) filter(where eligible_events=1)::int one_eligible_event,
  count(*) filter(where eligible_events between 2 and 4)::int two_to_four,
  count(*) filter(where eligible_events between 5 and 9)::int five_to_nine,
  count(*) filter(where eligible_events>=10)::int ten_plus,
  round(avg(eligible_events)::numeric,3) mean_eligible_events,
  percentile_cont(0.10) within group(order by eligible_events) p10,
  percentile_cont(0.25) within group(order by eligible_events) p25,
  percentile_cont(0.50) within group(order by eligible_events) p50,
  percentile_cont(0.75) within group(order by eligible_events) p75,
  percentile_cont(0.90) within group(order by eligible_events) p90
from per_person;

-- 3) Source-family coverage: events and people.
select
  e.source_family,
  count(*)::int raw_memberships,
  count(*) filter(where dem.snapshot_model_eligible)::int active_memberships,
  count(distinct e.person_id)::int people_any,
  count(distinct e.person_id) filter(where dem.snapshot_model_eligible)::int people_active
from research.dataset_event_membership dem
join research.life_events e on e.id=dem.event_id
where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
group by e.source_family
order by active_memberships desc,e.source_family;

-- 4) Domain coverage.
select
  e.domain,
  count(*)::int raw_memberships,
  count(*) filter(where dem.snapshot_model_eligible)::int active_memberships,
  count(distinct e.person_id) filter(where dem.snapshot_model_eligible)::int people_active
from research.dataset_event_membership dem
join research.life_events e on e.id=dem.event_id
where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
group by e.domain
order by active_memberships desc,e.domain;

-- 5) Wikipedia current/superseded revision audit.
with wiki as (
  select
    e.person_id,
    e.attributes->>'revision_id' revision_id,
    dem.snapshot_model_eligible,
    dem.exclusion_reason,
    e.event_key
  from research.dataset_event_membership dem
  join research.life_events e on e.id=dem.event_id
  where dem.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
    and e.source_family='wikipedia'
    and coalesce(e.extraction_method,'')='rule-from-revision-text'
)
select
  count(*)::int wikipedia_rule_memberships,
  count(*) filter(where snapshot_model_eligible)::int active_wikipedia_rule_events,
  count(*) filter(where exclusion_reason='superseded_by_v11_biography_revision')::int superseded_rule_events,
  count(distinct person_id)::int people_with_any_wikipedia_rule_event,
  count(distinct person_id) filter(where snapshot_model_eligible)::int people_with_active_wikipedia_rule_event,
  (
    select count(*)::int
    from (
      select person_id
      from wiki
      where snapshot_model_eligible
      group by person_id
      having count(distinct coalesce(revision_id,''))>1
    ) x
  ) people_with_multiple_active_revisions
from wiki;

-- 6) Hard leakage/intrinsic-invalid gates.
select
  count(*) filter(
    where dem.snapshot_model_eligible
      and e.observable_from>'2026-10-06'::date
  )::int active_after_cutoff,
  count(*) filter(
    where dem.snapshot_model_eligible
      and e.event_date_min>'2026-10-06'::date
  )::int active_event_start_after_cutoff,
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

-- 7) Candidate preservation and rule acceptance.
select
  count(*)::int v11_candidates,
  count(*) filter(where status='rule-accepted')::int rule_accepted,
  count(*) filter(where status<>'rule-accepted')::int retained_for_future_adjudication,
  count(distinct person_id)::int people_with_candidates
from research.event_candidates
where metadata ? 'v11_artifact_id';

-- 8) Coverage by birth era to expose observation bias.
with per_person as (
  select
    psf.person_id,
    (extract(year from psf.birth_date)::int/25)*25 birth_era_start,
    count(dem.event_id) filter(where dem.snapshot_model_eligible)::int eligible_events
  from research.person_snapshot_facts psf
  left join research.life_events e on e.person_id=psf.person_id
  left join research.dataset_event_membership dem
    on dem.dataset_snapshot_id=psf.dataset_snapshot_id
   and dem.event_id=e.id
  where psf.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
  group by psf.person_id,(extract(year from psf.birth_date)::int/25)*25
)
select
  birth_era_start,
  count(*)::int people,
  count(*) filter(where eligible_events>0)::int people_with_events,
  round(avg(eligible_events)::numeric,3) mean_events,
  percentile_cont(0.50) within group(order by eligible_events) median_events,
  percentile_cont(0.90) within group(order by eligible_events) p90_events
from per_person
group by birth_era_start
order by birth_era_start;

-- 9) Coverage by frozen birth geography group.
with per_person as (
  select
    psf.person_id,
    coalesce(psf.birth_geo_group,'__MISSING__') birth_geo_group,
    count(dem.event_id) filter(where dem.snapshot_model_eligible)::int eligible_events
  from research.person_snapshot_facts psf
  left join research.life_events e on e.person_id=psf.person_id
  left join research.dataset_event_membership dem
    on dem.dataset_snapshot_id=psf.dataset_snapshot_id
   and dem.event_id=e.id
  where psf.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
  group by psf.person_id,coalesce(psf.birth_geo_group,'__MISSING__')
)
select
  birth_geo_group,
  count(*)::int people,
  count(*) filter(where eligible_events>0)::int people_with_events,
  round(avg(eligible_events)::numeric,3) mean_events,
  percentile_cont(0.50) within group(order by eligible_events) median_events
from per_person
group by birth_geo_group
order by people desc,birth_geo_group;

-- 10) Compare v1.1 per-person active-event density against frozen v1.0.
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
), paired as (
  select
    p.id person_id,
    p.wikidata_id,
    coalesce(v10.n,0) v10_events,
    coalesce(v11.n,0) v11_events,
    coalesce(v11.n,0)-coalesce(v10.n,0) delta
  from research.people p
  join counts v10
    on v10.person_id=p.id
   and v10.dataset_snapshot_id='42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid
  join counts v11
    on v11.person_id=p.id
   and v11.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
)
select
  count(*)::int people,
  count(*) filter(where delta>0)::int people_gaining_active_events,
  count(*) filter(where delta=0)::int people_unchanged,
  count(*) filter(where delta<0)::int people_with_net_active_decrease,
  round(avg(delta)::numeric,3) mean_delta,
  percentile_cont(0.50) within group(order by delta) median_delta,
  percentile_cont(0.90) within group(order by delta) p90_delta,
  max(delta)::int max_delta
from paired;
