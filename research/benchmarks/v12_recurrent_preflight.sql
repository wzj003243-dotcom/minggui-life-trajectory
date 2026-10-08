-- Read-only preflight for recurrent documented events, NOT incidence of all life events.
-- Frozen snapshot must never be edited. This is the same cohort/split as Round 5.
-- A year is included only when the existing Round 5 observation window covers it.
-- Year-precision events crossing boundaries are deliberately not forced into one year.
WITH cohort AS (
  SELECT person_id, split_name, cutoff_date, observation_end_date
  FROM research.v11_r5_cutoffs WHERE cutoff_age = 18
), yearly AS (
  SELECT c.person_id, c.split_name, g.n AS year_index,
         (c.cutoff_date + make_interval(years => g.n))::date AS year_start,
         (c.cutoff_date + make_interval(years => g.n + 1))::date AS year_end
  FROM cohort c
  CROSS JOIN generate_series(0, 19) AS g(n)
  WHERE (c.cutoff_date + make_interval(years => g.n + 1))::date <= c.observation_end_date
), labels AS (
  SELECT y.person_id, y.split_name, y.year_index,
         count(e.canonical_event_key) AS n_events,
         count(DISTINCT e.domain) AS n_domains
  FROM yearly y
  LEFT JOIN research.snapshot_canonical_event_facts e
    ON e.dataset_snapshot_id = '7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
   AND e.snapshot_model_eligible
   AND e.person_id = y.person_id
   AND e.event_date_min >= y.year_start
   AND e.event_date_max < y.year_end
  GROUP BY y.person_id, y.split_name, y.year_index
)
SELECT split_name,
       count(*) AS eligible_person_years,
       count(*) FILTER (WHERE n_events > 0) AS years_with_documented_events,
       sum(n_events) AS canonical_events,
       count(*) FILTER (WHERE n_events > 1) AS years_with_multiple_events,
       round(avg(n_events)::numeric, 4) AS mean_documented_events_per_year
FROM labels
GROUP BY split_name ORDER BY split_name;
