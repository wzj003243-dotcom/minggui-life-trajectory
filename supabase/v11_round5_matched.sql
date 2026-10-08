-- v1.1 Round 5 matched-cohort, censor-aware training data.
-- Preregistered matched comparison: recompute event targets and history using
-- frozen canonical snapshot; retain v1.0 person cutoffs, observation windows,
-- and frozen person-level split.  Never mutate a frozen snapshot/dataset.
begin;

create table if not exists research.v11_r5_cutoffs (
  source_training_example_id bigint primary key,
  person_id bigint not null,
  wikidata_id text not null,
  cutoff_age int not null,
  cutoff_date date not null,
  information_cutoff date not null,
  observation_end_date date not null,
  split_name text not null,
  fold int,
  x_features_old jsonb not null,
  x_features_new jsonb not null,
  target_canonical_event_key text,
  target_domain text,
  target_observable_from date,
  old_target_canonical_event_key text,
  old_target_observable_from date,
  created_at timestamptz not null default now()
);
create table if not exists research.v11_r5_periods (
  person_period_id bigint primary key,
  source_training_example_id bigint not null references research.v11_r5_cutoffs(source_training_example_id),
  person_id bigint not null,
  cutoff_age int not null,
  interval_index int not null,
  interval_start_year int not null,
  interval_end_year int not null,
  interval_width_years int not null,
  interval_start_date date not null,
  interval_end_date date not null,
  outcome_class text not null,
  target_canonical_event_key text,
  target_domain text,
  target_observable_from date,
  observation_end_date date not null,
  old_outcome_class text,
  created_at timestamptz not null default now(),
  unique(source_training_example_id,interval_index)
);
create index if not exists v11_r5_periods_cutoff_idx on research.v11_r5_periods(source_training_example_id);
create index if not exists v11_r5_cutoffs_person_idx on research.v11_r5_cutoffs(person_id);

-- Refuse to materialize against a source snapshot that is no longer frozen
do $$
begin
  if not exists (
    select 1 from research.dataset_snapshots
    where id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
      and status='frozen'
      and canonical_event_sha256='2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf'
  ) then raise exception 'v1.1 frozen source fingerprint mismatch'; end if;
  if exists (select 1 from research.v11_r5_cutoffs)
     or exists (select 1 from research.v11_r5_periods)
  then raise exception 'refusing to overwrite existing Round 5 data'; end if;
end $$;

-- Materialize the two history feature arms with IDENTICAL extraction logic.
create temporary table r5_matched_histories on commit drop as
with origin as (
  select
    c.source_training_example_id,
    c.person_id,
    c.information_cutoff
  from research.trajectory_cutoff_matrix_v1 c
), snap as (
  select 'old'::text label,'42628250-3a51-4b92-b4bd-12c7dec846a8'::uuid id
  union all
  select 'new','7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
), grouped as (
  select
    c.source_training_example_id,s.label,
    e.domain,
    count(e.canonical_event_key)::int n,
    coalesce(sum(e.raw_event_count),0)::int nraw,
    max(e.observable_from) last_observed,
    count(distinct floor(e.age_mid/10.0))::int stages
  from origin c cross join snap s
  left join research.snapshot_canonical_event_facts e
    on e.dataset_snapshot_id=s.id
    and e.person_id=c.person_id
    and e.snapshot_model_eligible
    and e.observable_from<=c.information_cutoff
    and e.event_date_max<=c.information_cutoff
  group by c.source_training_example_id,s.label,e.domain
)
select
  source_training_example_id,label,
  sum(n)::int canonical_event_count,
  sum(nraw)::int raw_event_count,
  count(*) filter(where domain is not null)::int domain_count,
  sum(stages)::int life_stage_count,
  max(last_observed) last_observed,
  coalesce(jsonb_object_agg(domain,n) filter(where domain is not null),'{}'::jsonb) domain_counts
from grouped
group by source_training_example_id,label;
create unique index on r5_matched_histories(source_training_example_id,label);

insert into research.v11_r5_cutoffs (
  source_training_example_id,person_id,wikidata_id,cutoff_age,cutoff_date,
  information_cutoff,observation_end_date,split_name,fold,
  x_features_old,x_features_new,
  target_canonical_event_key,target_domain,target_observable_from,
  old_target_canonical_event_key,old_target_observable_from
)
select c.source_training_example_id,c.person_id,c.wikidata_id,c.cutoff_age,c.cutoff_date,
       c.information_cutoff,c.source_observation_end_date,a.split_name,a.fold,
       jsonb_set(c.x_features,'{history}',
         jsonb_build_object(
           'canonical_event_count',h0.canonical_event_count,
           'raw_event_count',h0.raw_event_count,
           'domain_count',h0.domain_count,
           'source_family_count',coalesce((c.x_features->'history'->>'source_family_count')::int,0),
           'life_stage_count',h0.life_stage_count,
           'summary',jsonb_build_object('domain_counts',h0.domain_counts,
             'last_observable_event_date',h0.last_observed)
         ),true),
       jsonb_set(c.x_features,'{history}',
         jsonb_build_object(
           'canonical_event_count',h1.canonical_event_count,
           'raw_event_count',h1.raw_event_count,
           'domain_count',h1.domain_count,
           'source_family_count',coalesce((c.x_features->'history'->>'source_family_count')::int,0),
           'life_stage_count',h1.life_stage_count,
           'summary',jsonb_build_object('domain_counts',h1.domain_counts,
             'last_observable_event_date',h1.last_observed)
         ),true),
       target.canonical_event_key,target.domain,target.observable_from,
       c.source_target_canonical_event_key,c.source_target_observable_from
from research.trajectory_cutoff_matrix_v1 c
join research.training_split_assignments a
  on a.training_dataset_id='8261f970-adc3-4f9a-8043-9e0f6cb90be8'::uuid
  and a.scenario_key='person_hash_v1'
  and a.person_id=c.person_id
join r5_matched_histories h0
  on h0.source_training_example_id=c.source_training_example_id and h0.label='old'
join r5_matched_histories h1
  on h1.source_training_example_id=c.source_training_example_id and h1.label='new'
left join lateral (
  select e.canonical_event_key,e.domain,e.observable_from
  from research.snapshot_canonical_event_facts e
  where e.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
    and e.person_id=c.person_id
    and e.snapshot_model_eligible
    and e.observable_from>c.information_cutoff
    and e.observable_from<=c.source_observation_end_date
    and e.event_date_max>c.information_cutoff
  order by e.observable_from,e.canonical_event_key
  limit 1
) target on true;

-- Exact fixed Round 4 risk grid, but v1.1 next-event label and censor time.
with grid as (
  select c.*,
         v.idx interval_index,v.a interval_start_year,v.b interval_end_year,
         (c.cutoff_date+make_interval(years=>v.a))::date d0,
         (c.cutoff_date+make_interval(years=>v.b))::date d1
  from research.v11_r5_cutoffs c
  cross join (values (0,0,1),(1,1,3),(2,3,5),(3,5,10),(4,10,20)) v(idx,a,b)
), eligible as (
  select g.*
  from grid g
  where (g.target_observable_from is null or g.target_observable_from>g.d0)
    and (
      (g.target_observable_from is not null and g.target_observable_from<=g.d1)
      or g.observation_end_date>=g.d1
    )
)
insert into research.v11_r5_periods (
  person_period_id,source_training_example_id,person_id,cutoff_age,
  interval_index,interval_start_year,interval_end_year,interval_width_years,
  interval_start_date,interval_end_date,outcome_class,
  target_canonical_event_key,target_domain,target_observable_from,observation_end_date
)
select row_number() over(order by source_training_example_id,interval_index)::bigint,
       source_training_example_id,person_id,cutoff_age,
       interval_index,interval_start_year,interval_end_year,
       interval_end_year-interval_start_year,d0,d1,
       case when target_observable_from is not null and target_observable_from<=d1
            then case when target_domain in ('career','recognition','relationship')
              then target_domain else 'other' end
            else 'no_event' end,
       target_canonical_event_key,target_domain,target_observable_from,observation_end_date
from eligible;

commit;

select 'cutoffs' item,count(*)::int n from research.v11_r5_cutoffs
union all select 'periods',count(*)::int from research.v11_r5_periods
union all select 'event_periods',count(*)::int from research.v11_r5_periods where outcome_class<>'no_event';

