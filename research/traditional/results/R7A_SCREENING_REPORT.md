# R7A screening report — annual branch clashes natal day branch

**Status:** exploratory feasibility screen completed; **NO affirmative incremental prediction result**. 2026-10-08.

## Frozen protocol and changes from initial plan

- Primary detailed protocol was frozen in `R7A_ANNUAL_BRANCH_CLASH_PREREG.md` **before examining outcomes**.
- Two attempts to execute its fully adjusted per-person-year SQL timed out at the database statement limit. These attempts produced **no scores**.
- A reduced, age-stratified **feasibility screen** was then substituted. Its query and evaluation code are committed. This is **not** a completed preregistered confirmatory test and must not be advertised as one.
- Results cover the split-fixed `train` and `validation` cohorts only from v1.1; earlier R4/R5 test data were not used or opened for this analysis.
- Canonical events are observed from historical biographies, not real-life events, and are not prospective.

## Sources and definitions

- Frozen source snapshot: `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`.
- Exposure: calendar-year predominant solar-year branch (1984 as 甲子 / 子), compared with frozen natal `four_pillars.day_zhi`, branch opposition at +6 mod 12. Year assignments are approximate for Jan/early Feb.
- Negative controls: substitute +1, +3 and +5 annual calendar years, same model capacity and target years.
- Outcomes: one or more recorded `relationship.marriage`, `relationship.divorce`, `relationship.spouse.start/end` OR career position/team/employer start/end, appointment, role start or retirement events during the full Gregorian calendar year.
- Only events whose historical date interval is inside one Gregorian year were counted. Years intersecting boundary-crossing uncertain event date intervals were excluded.
- Model: age-decade empirical occurrence rates (train) with fixed 200-pseudoyear global prior shrinkage, then age × clash/no-clash rates with identical fixed shrinkage. This **does not** control prior history or natal day-branch main effects adequately and is not the full planned analysis.

## Sample size

| Group | Eligible person-calendar-years |
|---|---:|
| Train | 115,288 |
| Validation | 24,464 |

In validation, 816 person-years had at least one targeted career event, 225 at least one relationship event. These can overlap.

## Validation binary log-loss (lower is better)

| Target | Age-only | True annual clash | +1-year placebo | +3-year placebo | +5-year placebo |
|---|---:|---:|---:|---:|---:|
| Career | 0.145763433 | 0.145819227 | 0.145816688 | 0.145838351 | 0.145776088 |
| Relationship | 0.050732262 | 0.050720951 | 0.050740151 | 0.050726070 | 0.050740937 |

Validation binary Brier:

| Target | Age-only | True annual clash | +1 placebo | +3 placebo | +5 placebo |
|---|---:|---:|---:|---:|---:|
| Career | 0.032222391 | 0.032225453 | 0.032225742 | 0.032226539 | 0.032224626 |
| Relationship | 0.009085716 | 0.009085631 | 0.009086173 | 0.009085577 | 0.009086315 |

Adding the real clash indicator **worsened career scores** slightly. Relationship had a tiny unverified apparent improvement; a shifted placebo also exhibited improvement. The four-feature screen does **not** pass the preregistered requirement of a gain in both domains, and no uncertainty estimate/independent cohort is available.

**Conclusion: there is presently no reliable evidence that this one rule improves annual documented-event predictions.** This is **not a test of full BaZi × DaYun × annual rules**, and cannot establish any verdict on all traditional methods.

## Reproduce without licensing-restricted birth records

SQL: `research/traditional/r7a_fast_age_stratified_screen.sql` (database read-only).
Stored 14 aggregate age-split groups: `research/traditional/results/r7a_fast_age_aggregates.json`.
Offline evaluator: `python research/traditional/evaluate_r7a_fast.py research/traditional/results/r7a_fast_age_aggregates.json /tmp/r7a-replayed.json`.
Regression checks: `python -m unittest discover -s tests -p 'test_evaluate_r7a_fast.py' -v`.

## What should be tested next

1. Independently compute **actual start age, direction and each DaYun decade** from checked birth time, locality and solar terms; include school/sect choice and cross-check conversion. Do **not** impute missing times or set cycles post hoc.
2. Use event-month/day precision for a proper **Li-Chun-based** temporal experiment; year-only records need interval-censored likelihood or time uncertainty integration.
3. Fit the preregistered **age/history + natal main-effect baseline** and compare **additive natal/DaYun/annual** versus interaction model on a new external person-disjoint holdout.
4. Re-run H1/H2/H3/H4 with person-bootstrap uncertainty, shifted-cycle nulls, realistic documentation-propensity and era/geography controls. Never give the rule a predictive weight before it passes these tests.

**Product implication:** keep the traditional interpretation as a clearly labeled symbolic view. Current actual forecasting weights remain purely data-driven.