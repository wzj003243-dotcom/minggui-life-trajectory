# R7B preregistration — interacting natal context with annual branch clash

**Frozen before outcome retrieval: October 14, 2026.**
**Development only. NOT a full DaYun/BaZi test, NOT a new independent holdout, and NOT proof of fortune telling.**

## Question

Test whether the traditional annual-branch-vs-natal-day-branch clash indicator contributes to predicting *recorded* career/relationship changes when conditioned on **two prespecified natal context variables**:

1. Day-master element, one of 木火土金水 (computed from frozen natal day stem).
2. Natal month branch clashes natal day branch (binary, 6 classical opposing pairs).

This is a two-factor natal context × annual condition. **DaYun is NOT in this R7B experiment**; it needs real verified onset, cycle direction and calendar timing and must be tested separately. No sign ("good"/"bad") or outcome direction is assumed.

## Historical data

Frozen v1.1 canonical snapshot `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`. Reuse fixed age-18 R5 train and validation *people only* (no old already examined test set). Source is selected notable-person biographies, not a population event registry. AA/A/B Astro-Databank birth-time quality does not cure sample selection.

A row = full Gregorian Jan–Dec person-year age 18..87 fully within fixed observational followup, excluding years where canonical events span Gregorian year boundary. Both labels use documented events with min/max date wholly in the same year. 9 career types and 4 relationship types are fixed exactly as R7A; recorded-absence is not actual nonevent. Calendar proxy: year branch derived as (Gregorian year − 1984) mod 12; Jan/early-Feb convention mismatches LiChun for some events and is a known limitation.

## Predefined models and tests

For each domain separately:
- A: age-decade lookup (200 pseudoyear shrinkage to train global rate).
- B: age × day-element × natal month/day clash, smoothed 200 pseudoyears to A (static natal-context baseline).
- C: B + true annual/day-branch clash indicator, smoothed 200 pseudoyears toward B.
- D1/D3/D5: same as C but shifted annual branch +1/+3/+5 years as fixed placebos.

Rows and split membership identical across arms. No tuning using validation labels. Sparse modifier strata with zero train person-year exposure inherit the parent prior. Primary metric validation binary log-loss (lower is better); Brier secondary. **Gate:** C must outperform B and every shifted placebo in **both** relationship and career; otherwise no evidence for predictive increment under this screen. Report raw sample/event counts per group and all controls, never selectively report only a positive domain. No interpretation of a p-value; bootstrap at *person* level unavailable with published aggregate-only rows, so significance is not established.

A better gain cannot be described as discovering traditional "命运规律" because historical era/occupation/time publication/documentation remain uncontrolled. The additive vs interaction comparison is exploratory. Next must use true LiChun event-time uncertainty, dynamic audited DaYun start, fresh external people, and person-cluster uncertainty.

## Security and replay

SQL outputs aggregate-only grouped counts. Do not publish individual timed birth records, person IDs, natal individual pillars or licensed Astro-Databank birth dates to the public repo. Freeze code, data outputs and checksums in a Draft PR. A future model receiving traditional predictive weights requires external replication; current user-facing symbolic demo will display **rule activation not validated event probabilities**.
