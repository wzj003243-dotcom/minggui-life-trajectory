-- R7A preregistered screen. Frozen v1.1, training and validation people ONLY.
-- The annual Ganzhi *branch* is a Gregorian majority-year proxy (after Li Chun).
-- Dates in Jan/early Feb may belong to prior solar year: NOT definitive BaZi.
-- No person-level licensed birth records are exported. This query returns aggregates.
WITH cohort AS (
 SELECT person_id,split_name,cutoff_date,observation_end_date,
        x_features_new->'four_pillars'->>'day_zhi' AS day_branch
 FROM research.v11_r5_cutoffs
 WHERE cutoff_age=18 AND split_name IN ('train','validation')
), facts AS (
 SELECT e.person_id,e.event_type,e.event_date_min,e.event_date_max,e.observable_from,
        extract(year from e.event_date_min)::int first_year,
        extract(year from e.event_date_max)::int last_year,
        greatest(
          extract(year from e.event_date_max)::int+1,
          extract(year from e.observable_from)::int+
          CASE WHEN extract(month from e.observable_from)=1 AND
                    extract(day from e.observable_from)=1 THEN 0 ELSE 1 END
        )::int ready_year
 FROM research.snapshot_canonical_event_facts e
 JOIN cohort c ON c.person_id=e.person_id
 WHERE e.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
   AND e.snapshot_model_eligible
), event_years AS (
 SELECT person_id,first_year yr,
     count(*) FILTER(WHERE event_type IN (
       'relationship.marriage','relationship.divorce',
       'relationship.spouse.start','relationship.spouse.end'
     ))::int relationship_events,
     count(*) FILTER(WHERE event_type IN (
       'career.position.start','career.position.end','career.team.start',
       'career.team.end','career.employer.start','career.employer.end',
       'career.appointment','career.role_start','career.retirement'
     ))::int career_events
 FROM facts WHERE first_year=last_year
 GROUP BY 1,2
), ambiguous_years AS (
 SELECT f.person_id,g.yr,count(*)::int n
 FROM facts f
 CROSS JOIN LATERAL generate_series(f.first_year,f.last_year) g(yr)
 WHERE f.first_year!=f.last_year GROUP BY 1,2
), ready_years AS (
 SELECT person_id,ready_year yr,count(*)::int newly_available
 FROM facts GROUP BY 1,2
), expanded_years AS (
 SELECT c.person_id,c.split_name,c.cutoff_date,c.observation_end_date,c.day_branch,
        yy.yr,make_date(yy.yr,1,1) d0,make_date(yy.yr+1,1,1) d1,
        coalesce(ready.newly_available,0) newly_available
 FROM cohort c
 CROSS JOIN LATERAL generate_series(
   extract(year from c.cutoff_date)::int-18,
   extract(year from c.observation_end_date)::int
 ) yy(yr)
 LEFT JOIN ready_years ready ON ready.person_id=c.person_id AND ready.yr=yy.yr
 WHERE strpos('子丑寅卯辰巳午未申酉戌亥',c.day_branch)>0
), years_with_history AS (
 SELECT x.*,
        sum(newly_available) OVER(PARTITION BY person_id ORDER BY yr
                                 ROWS UNBOUNDED PRECEDING)::int AS hn
 FROM expanded_years x
), annual AS (
 SELECT y.person_id,y.split_name,y.day_branch,y.yr,y.hn,
        y.yr-extract(year from y.cutoff_date)::int+17
          + CASE WHEN extract(month from y.cutoff_date)=1 AND extract(day from y.cutoff_date)=1
                 THEN 1 ELSE 0 END AS age,
        coalesce(ev.relationship_events,0)::int relationship_events,
        coalesce(ev.career_events,0)::int career_events,
        coalesce(amb.n,0)::int ambiguities
 FROM years_with_history y
 LEFT JOIN event_years ev ON ev.person_id=y.person_id AND ev.yr=y.yr
 LEFT JOIN ambiguous_years amb ON amb.person_id=y.person_id AND amb.yr=y.yr
 WHERE y.d0>=y.cutoff_date AND y.d1<=y.observation_end_date
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