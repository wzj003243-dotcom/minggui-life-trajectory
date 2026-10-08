-- R7A LIGHTWEIGHT FEASIBILITY SCREEN, NOT the preregistered R7A formal model.
-- Age-stratified aggregate only. Not sufficient for claims about actual fate.
-- Prenatal day branch and year proxy; birthplace/hour metadata stay private.
WITH cohort AS (
 SELECT person_id,split_name,cutoff_date,observation_end_date,
        x_features_new->'four_pillars'->>'day_zhi' day_branch
 FROM research.v11_r5_cutoffs
 WHERE cutoff_age=18 AND split_name IN ('train','validation')
), source_events AS (
 SELECT e.person_id,
        extract(year from e.event_date_min)::int first_year,
        extract(year from e.event_date_max)::int last_year,
        e.event_type
 FROM research.snapshot_canonical_event_facts e
 JOIN cohort c USING(person_id)
 WHERE e.dataset_snapshot_id='7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid
   AND e.snapshot_model_eligible
), exact_years AS (
 SELECT person_id,first_year yr,
  max((event_type IN (
     'relationship.marriage','relationship.divorce',
     'relationship.spouse.start','relationship.spouse.end'
   ))::int)::int rel_events,
  max((event_type IN (
     'career.position.start','career.position.end',
     'career.team.start','career.team.end',
     'career.employer.start','career.employer.end',
     'career.appointment','career.role_start','career.retirement'
  ))::int)::int car_events
 FROM source_events
 WHERE first_year=last_year
 GROUP BY 1,2
), uncertain_years AS (
 SELECT person_id,first_year yr FROM source_events WHERE first_year<>last_year
 UNION
 SELECT person_id,last_year yr FROM source_events WHERE first_year<>last_year
), person_calendar_year AS (
 SELECT c.split_name,c.day_branch,g.yr,
        g.yr-extract(year from c.cutoff_date)::int+17+
        CASE WHEN extract(month from c.cutoff_date)=1 AND extract(day from c.cutoff_date)=1
        THEN 1 ELSE 0 END AS age,
        coalesce(ey.rel_events,0)::int rel_events,
        coalesce(ey.car_events,0)::int car_events
 FROM cohort c
 CROSS JOIN LATERAL generate_series(
     extract(year from c.cutoff_date)::int,
     least(extract(year from c.observation_end_date)::int,
           extract(year from c.cutoff_date)::int+71)
 ) g(yr)
 LEFT JOIN exact_years ey ON ey.person_id=c.person_id AND ey.yr=g.yr
 LEFT JOIN uncertain_years uy ON uy.person_id=c.person_id AND uy.yr=g.yr
 WHERE make_date(g.yr,1,1)>=c.cutoff_date
   AND make_date(g.yr+1,1,1)<=c.observation_end_date
   AND strpos('子丑寅卯辰巳午未申酉戌亥',c.day_branch)>0
   AND uy.person_id IS NULL
), risk AS (
 SELECT split_name,day_branch,yr,rel_events,car_events,
 CASE WHEN age<28 THEN '18-27' WHEN age<38 THEN '28-37'
      WHEN age<48 THEN '38-47' WHEN age<58 THEN '48-57'
      WHEN age<68 THEN '58-67' WHEN age<78 THEN '68-77'
      ELSE '78-87' END AS age_band
 FROM person_calendar_year WHERE age BETWEEN 18 AND 87
)
SELECT split_name,age_band,count(*)::int n,
       sum(rel_events)::int relationship_cases,
       sum(car_events)::int career_cases,
       count(*) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+0))%12+12)%12=6))::int AS exposure_0,
       sum(p.rel_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+0))%12+12)%12=6))::int AS relationship_0,
       sum(p.car_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+0))%12+12)%12=6))::int AS career_0,
       count(*) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+1))%12+12)%12=6))::int AS exposure_1,
       sum(p.rel_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+1))%12+12)%12=6))::int AS relationship_1,
       sum(p.car_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+1))%12+12)%12=6))::int AS career_1,
       count(*) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+3))%12+12)%12=6))::int AS exposure_3,
       sum(p.rel_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+3))%12+12)%12=6))::int AS relationship_3,
       sum(p.car_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+3))%12+12)%12=6))::int AS career_3,
       count(*) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+5))%12+12)%12=6))::int AS exposure_5,
       sum(p.rel_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+5))%12+12)%12=6))::int AS relationship_5,
       sum(p.car_events) FILTER (WHERE (((strpos('子丑寅卯辰巳午未申酉戌亥',p.day_branch)-1-(p.yr-1984+5))%12+12)%12=6))::int AS career_5
FROM risk p
GROUP BY 1,2 ORDER BY 1,2;