# R7A locked screening protocol — annual branch clash × natal day branch

**Status:** preregistered before R7A outcome query execution, 2026-10-08. A development-only falsification screen; NOT full BaZi/DaYun and NOT out-of-sample proof.

## Question

Traditional descriptive hypothesis H1: does a calendar-year branch that clashes with a person's *natal day branch* carry incremental association with subsequently documented **relationship transition** and **career transition** events, after baseline prior history and birth structure?

This is NOT a claim that a clash means bad fortune. A positive finding would only support further validation, not causal power or daily-life predictions.

## Source and fixed cohort

- Frozen snapshot v1.1 `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`.
- R5 age-18 cohort, person-disjoint **train and validation only**. No R4/R5 previously used `test` people.
- All people have minute-precision AA/A/B birth records *according to source metadata*, from `astro-databank-timed`. Thus sample is strongly selected and publication rights must be respected. NO identifiable or licensed birth records exported by this experiment.
- Full **Gregorian calendar years** whose Jan1–Dec31 span is after the person's 18th-birthday cutoff and before source observation end; ages 18..87.
- Historical facts are grouped to a whole Gregorian year only if `event_date_min>=Jan1` and `event_date_max<next Jan1`. Exclude years with events whose uncertainty intervals span a year boundary rather than labeling those episodes no-event. Use `e.observable_from<=Jan1` additionally for prior history features.
- The year of the solar-terms BaZi year is represented by its **post-Li-Chun predominant Gregorian-year branch** (1984=甲子, yearly +1). Critical limitation: events in January / early February can belong to the *preceding* BaZi year. Because many source events have only year precision, these cannot be safely assigned to the true solar-term year. Therefore the result is a noisy **annual calendar-year proxy screen**, not a formally dated BaZi annual prediction test.

## Primary event labels, fixed

- `relationship_transition`: binary 1 if the year contains `relationship.marriage`, `relationship.divorce`, `relationship.spouse.start`, or `relationship.spouse.end`; multiple records in a year count only once.
- `career_transition`: binary 1 if year contains career position/team/employer starts/ends, appointment, role start or retirement; once/year binary.
- Absence of documented events is **NOT** evidence nothing happened. This is a retrospective documentation experiment.

## Exposure and controls

- Natal day branch directly from frozen `four_pillars.day_zhi` (no post hoc hour selection).
- True clash: annual zodiac branch is exactly opposite the natal day branch on 12-branch cycle (`+6 mod 12`).
- Predeclared placebo clashes: replace annual branch by **+1**, **+3** and **+5** years; same other data and model capacity.
- For each target, train on identical rows:
  1. baseline age decade (18–27, ... 78–87) + four bins pre-year history count (0/1/2–4/5+) + natal day branch;
  2. baseline + binary *true* annual-day branch clash;
  3. baseline + one of the three *shifted* clash indicators.
- Lookup shrinkage: `k=200` pseudoyears at each level; global prevalence → age/history → age/history/day_branch → clash flag. No fitting on validation labels. Identical train and validation exposure across arms.
- Metric: validation **binary log-loss** and Brier, career and relationship **separately**. A smaller score is better.
- Do not tune `k`, event classes, date windows, branch shifts, or select the most favorable domain based on validation results.
- Primary decision screen: true clash arm must outperform baseline **and every placebo** for BOTH target types to justify further evaluation. If one or both fail, outcome is negative/inconclusive under this precise noisy proxy, not a proof traditional philosophy is false.
- Even a screen-positive result is exploratory until another untouched person-disjoint and era/geography cohort, person-cluster bootstrap intervals, source publication replay and exact Li-Chun boundary assignment verify it.

## Next after screening

If the data quality screen is feasible, implement independently computed real DaYun onset with correct solar-term method and birth precision; do not substitute age-mod-10 cycles or infer from the person's future biography. A genuine (natal × DaYun × annual) test must separately preregister its joint hypotheses. Tests of just annual-day clash MUST NOT be described as testing complete traditional fortune telling.

**Ethics:** all conclusions are about statistically recorded events in a selected historical sample, never a person's fate; do not elevate numerology-derived statistics over real-world risk and choices.