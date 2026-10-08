-- R7A preregistered screen. Frozen v1.1, training and validation people ONLY.
-- The annual Ganzhi *branch* is a Gregorian majority-year proxy (after Li Chun).
-- Dates in Jan/early Feb may belong to prior solar year: NOT definitive BaZi.
-- No person-level licensed birth records are exported. This query returns aggregates.
WITH cohort AS (
 SELECT person_id,split_name,cutoff_date,observation_end_date,
        x_features_new->'four_pillars'->>'day_zhi' AS day_branch
 FROM research.v11_r5_cutoffs
 WHERE cutoff_age=18 AND split_name IN ('train','validation')
), candidate_years AS (
 SELECT c.person_id,c.split_name,c.cutoff_date,c.observation_end_date,c.day_branch,
        yrs.yr,
        make_date(yrs.yr,1,1) AS d0,make_date(yrs.yr+1,1,1) AS d1,
        yrs.yr - extract(year from c.cutoff_date)::int + 17
        + CASE WHEN extract(month from c.cutoff_date)=1
                     AND extract(day from c.cutoff_date)=1 THEN 1 ELSE 0 END AS age
 FROM cohort c
 CROSS JOIN LATERAL generate_series(
   extract(year from c.cutoff_date)::int,
   least(extract(year from c.observation_end_date)::int,extract(year from c.cutoff_date)::int+71)
 ) yrs(yr)
 WHERE make_date(yrs.yr,1,1)>=c.cutoff_date
   AND make_date(yrs.yr+1,1,1)<=c.observation_end_date
   AND strpos('子丑寅卯辰巳午未申酉戌亥',c.day_branch)>0
), annual AS (
 SELECT y.person_id,y.split_name,y.day_branch,y.yr,y.age,y.d0,y.d1,
  count(e.canonical_event_key) FILTER(
    WHERE e.event_date_max<y.d0 AND e.observable_from<=y.d0
  )::int AS hn,
  count(e.canonical_event_key) FILTER(
    WHERE e.event_date_min<y.d1 AND e.event_date_max>=y.d0
      AND (e.event_date_min<y.d0 OR e.event_date_max>=y.d1)
  )::int AS ambiguities,
  count(e.canonical_event_key) FILTER(
    WHERE e.event_date_min>=y.d0 AND e.event_date_max<y.d1
      AND e.event_type IN (
        'relationship.marriage','relationship.divorce',
        'relationship.spouse.start','relationship.spouse.end'
      )
  )::int AS relationship_events,
  count(e.canonical_event_key) FILTER(
    WHERE e.event_date_min>=y.d0 AND e.event_date_max<y.d1
      AND e.event_type IN (
        'career.position.start','career.position.end','career.team.start',
        'career.team.end','career.employer.start','career.employer.end',
        'career.appointment','career.role_start','career.retirement'
      )
  )::int AS career_events
 FROM candidate_years y
 LEFT JOIN research.snapshot_canonical_event_facts e
   ON e.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
   AND e.snapshot_model_eligible AND e.person_id=y.person_id
   AND (
      (e.event_date_max<y.d0 AND e.observable_from<=y.d0)
      OR (e.event_date_min<y.d1 AND e.event_date_max>=y.d0)
   )
 GROUP BY y.person_id,y.split_name,y.day_branch,y.yr,y.age,y.d0,y.d1
), rows AS (
 SELECT person_id,split_name,day_branch,yr,
  CASE WHEN age<28 THEN '18-27' WHEN age<38 THEN '28-37'
       WHEN age<48 THEN '38-47' WHEN age<58 THEN '48-57'
       WHEN age<68 THEN '58-67' WHEN age<78 THEN '68-77'
       ELSE '78-87' END AS age_band,
  CASE WHEN hn=0 THEN '0' WHEN hn=1 THEN '1'
       WHEN hn<5 THEN '2-4' ELSE '5+' END AS hist_band,
  (strpos('子丑寅卯辰巳午未申酉戌亥',day_branch)-1)::int AS day_idx,
  (relationship_events>0)::int AS relationship,
  (career_events>0)::int AS career
 FROM annual
 WHERE age>=18 AND age<=87 AND ambiguities=0
), data AS (
 SELECT r.*,v.domain,v.outcome
 FROM rows r
 CROSS JOIN LATERAL (VALUES ('relationship',r.relationship),('career',r.career)) v(domain,outcome)
), globally AS (
 SELECT domain,sum(outcome)::numeric/count(*) AS p FROM data
 WHERE split_name='train' GROUP BY domain
), agehist AS (
 SELECT domain,age_band,hist_band,count(*)::numeric n,sum(outcome)::numeric k
 FROM data WHERE split_name='train' GROUP BY 1,2,3
), agehist_rate AS (
 SELECT a.*, (a.k+200*g.p)/(a.n+200) AS p
 FROM agehist a JOIN globally g USING(domain)
), natal AS (
 SELECT domain,age_band,hist_band,day_branch,count(*)::numeric n,sum(outcome)::numeric k
 FROM data WHERE split_name='train' GROUP BY 1,2,3,4
), natal_rate AS (
 SELECT x.*, (x.k+200*a.p)/(x.n+200) AS p
 FROM natal x JOIN agehist_rate a USING(domain,age_band,hist_band)
), shifted AS (
 SELECT d.*, sh.offset_year,
   (((d.day_idx-(d.yr-1984+sh.offset_year))%12+12)%12=6) AS clash
 FROM data d CROSS JOIN (VALUES (0),(1),(3),(5)) sh(offset_year)
), joint AS (
 SELECT offset_year,domain,age_band,hist_band,day_branch,clash,
        count(*)::numeric n,sum(outcome)::numeric k
 FROM shifted WHERE split_name='train' GROUP BY 1,2,3,4,5,6
), joint_rate AS (
 SELECT j.*, (j.k+200*n.p)/(j.n+200) AS p
 FROM joint j JOIN natal_rate n USING(domain,age_band,hist_band,day_branch)
), prediction AS (
 SELECT d.domain,d.offset_year,d.outcome,d.clash,
        greatest(1e-9,least(1-1e-9,n.p)) AS p0,
        greatest(1e-9,least(1-1e-9,coalesce(j.p,n.p))) AS p1
 FROM shifted d JOIN natal_rate n USING(domain,age_band,hist_band,day_branch)
 LEFT JOIN joint_rate j USING(offset_year,domain,age_band,hist_band,day_branch,clash)
 WHERE d.split_name='validation'
)
SELECT domain,offset_year,count(*)::int n,
       sum(outcome)::int positives,count(*) FILTER(WHERE clash)::int clash_years,
       sum(outcome) FILTER(WHERE clash)::int clash_positive,
       round(avg(-outcome*ln(p0)-(1-outcome)*ln(1-p0))::numeric,9) baseline_logloss,
       round(avg(-outcome*ln(p1)-(1-outcome)*ln(1-p1))::numeric,9) interaction_logloss,
       round((avg(-outcome*ln(p1)-(1-outcome)*ln(1-p1))
             -avg(-outcome*ln(p0)-(1-outcome)*ln(1-p0)))::numeric,9) delta_logloss,
       round(avg((outcome-p0)^2)::numeric,9) baseline_brier,
       round(avg((outcome-p1)^2)::numeric,9) interaction_brier,
       round((avg((outcome-p1)^2)-avg((outcome-p0)^2))::numeric,9) delta_brier
FROM prediction GROUP BY domain,offset_year ORDER BY domain,offset_year;