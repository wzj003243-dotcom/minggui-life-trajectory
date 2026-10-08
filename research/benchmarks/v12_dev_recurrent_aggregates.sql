-- DEV-ONLY preregistered aggregation for R6, prior to any test inspection.
-- All training/evaluation is only on frozen v1.1 train/validation people.
-- Observation scope: DOCUMENTED canonical events, not actual absence of life events.
-- Labels crossing person-year bounds are excluded as ambiguous.
-- Exact output columns consumed by fit_recurrent_lookup.py.
WITH c AS (
  SELECT person_id,split_name,cutoff_date,observation_end_date
  FROM research.v11_r5_cutoffs
  WHERE cutoff_age=18 AND split_name IN ('train','validation')
),
y AS (
  SELECT c.person_id,c.split_name,g.i,
     (c.cutoff_date+make_interval(years=>g.i))::date a,
     (c.cutoff_date+make_interval(years=>g.i+1))::date b
  FROM c CROSS JOIN generate_series(0,19) g(i)
  WHERE (c.cutoff_date+make_interval(years=>g.i+1))::date<=c.observation_end_date
),
f AS (
  SELECT y.person_id,y.split_name,y.i,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_max<y.a AND e.observable_from<=y.a
    )::int hn,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_min<y.b AND e.event_date_max>=y.a
      AND (e.event_date_min<y.a OR e.event_date_max>=y.b)
    )::int amb,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_min>=y.a AND e.event_date_max<y.b AND e.domain='career'
    )::int c,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_min>=y.a AND e.event_date_max<y.b AND e.domain='recognition'
    )::int r,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_min>=y.a AND e.event_date_max<y.b AND e.domain='relationship'
    )::int rel,
    count(e.canonical_event_key) FILTER (
      WHERE e.event_date_min>=y.a AND e.event_date_max<y.b
      AND e.domain NOT IN ('career','recognition','relationship')
    )::int o
  FROM y LEFT JOIN research.snapshot_canonical_event_facts e
    ON e.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
    AND e.snapshot_model_eligible AND e.person_id=y.person_id
  GROUP BY y.person_id,y.split_name,y.i
),
b AS (
  SELECT split_name,
  CASE WHEN i<7 THEN '18-24' WHEN i<12 THEN '25-29'
       WHEN i<17 THEN '30-34' ELSE '35-37' END age_band,
  CASE WHEN hn=0 THEN '0' WHEN hn=1 THEN '1'
       WHEN hn<5 THEN '2-4' ELSE '5+' END hist_band,
  c,r,rel,o,amb
  FROM f
)
SELECT split_name,age_band,hist_band,count(*)::int n,
  sum((c>0)::int)::int cp,sum(c)::int cc,
  sum((r>0)::int)::int rp,sum(r)::int rc,
  sum((rel>0)::int)::int lp,sum(rel)::int lc,
  sum((o>0)::int)::int op,sum(o)::int oc
FROM b WHERE amb=0 GROUP BY split_name,age_band,hist_band
ORDER BY split_name,age_band,hist_band;
