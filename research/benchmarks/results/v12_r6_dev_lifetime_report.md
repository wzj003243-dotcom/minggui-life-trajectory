# R6 development result — fitted recurrent documentary-event lifetime baseline

**Date:** 2026-10-08
**Status:** Reproducible train/validation **development experiment**, not a fresh independent held-out test or validated lifetime forecasting.
**Frozen input snapshot:** v1.1 \`7fce3b79-ebfc-40b2-a5f0-e91b28db6a02\`.
**Protocol:** \`minggui-r6-annual-recurrent-lookup-dev-v1\`.

## What was built

- An **annual recurrent-event intensity** model, covering ages **18–87**, with age-specific and prior-history-conditioned expected counts of *documented* career, recognition, relationship, and other canonical life events.
- A basic Poisson Monte Carlo multi-path simulator that recalculates intensities each year after sampling preceding documented events.
- **Fixed pseudoyear shrinkage strength = 200**, no hyperparameter optimization on validation.
- Three arms using **identical target definitions and eligible person-years**:
  1. age only;
  2. age + **any previous documented event** (coverage-proxy control);
  3. age + 4 bins of previous documented event counts (0 / 1 / 2–4 / ≥5).
- Source SQL, frozen aggregate inputs, JSON fitted model, simulator integration and regression tests.

## Freeze and sample protocol

The age-18 original-cutoff cohort and person-level splits come from Round 5, without modifying any frozen snapshot. Only \`train\` and \`validation\` persons were inspected for model development; the earlier Round 4/5 \`test\` people are explicitly excluded. However, that test group has previously been examined in prior rounds and is **not a fresh R6 independent sample**.

- Train: 2,339 individuals; **100,771** unambiguously dated, administratively followed-up person-years.
- Validation: 506 individuals; **21,449** comparable person-years.
- Age 18–87 bins: 18–27, 28–37, 38–47, 48–57, 58–67, 68–77, 78–87.
- Raw full-window eligible exposure before date-boundary ambiguity exclusion: 116,600 train and 24,767 validation person-years.
- 15,829 train years and 3,318 validation years excluded when a model-eligible event's date uncertainty crosses the annual window. The exclusion can itself bias which event-positive periods remain.
- Counts use frozen model-eligible canonical events whose entire historical event date interval falls within the followed-up year. Source *silence* is not proof of absence.
- Historical features use event max date before the current year and \`observable_from <= year_start\`; this is an optimistic retrospective protocol, **not** guaranteed historically publication-timestamp-accurate.

## Development validation scores (lower is better)

This is **mean of four domain-specific** annual binary log-loss / Brier metrics (not R5 multiclass log-loss; do not compare their absolute scales).

| Feature arm | Macro annual log-loss | Macro annual Brier |
| --- | ---: | ---: |
| Age-only | **0.037858** | 0.006433 |
| Age + any prior recorded event | **0.035027** | 0.006390 |
| Age + prior recorded event count bins | **0.033612** | **0.006371** |

- Age + count bins shows **11.2% relative macro log-loss reduction** vs age-only.
- Any-history alone explains **most of the absolute reduction**. Documentation density, prestige, source availability and historical selection could explain some or all of the apparent signal; no causal inference is justified.
- Brier improvement is small in absolute terms and significance was not assessed.
- Held-out validation event counts across 21,449 person-years: career 346, recognition 48, relationship 28, other 492. The rare categories do not support high-confidence personalization.

Per-domain annual **binary log-loss**:

| Domain | Age-only | Age + count history |
| --- | ---: | ---: |
| Career | 0.058273 | 0.052023 |
| Recognition | 0.014984 | 0.014359 |
| Relationship | 0.009943 | 0.009888 |
| Other | 0.068231 | 0.058176 |

The log-loss reduction only establishes an empirical association between previous recorded history and future *recorded* events within this retrospectively curated celebrity sample. Most annual rows contain zero observed canonical events. Multi-event count calibration, pathwise correlations, cumulative 10+ year trajectory coverage and independent external validity have not been demonstrated.

## Model artifacts

- SQL: \`research/benchmarks/v12_dev_lifetime_aggregates.sql\`
- Frozen aggregate counts: \`research/benchmarks/data/v12_r6_dev_lifetime_aggregates.json\`
- Fitted lookup rates + development validation scores: \`research/benchmarks/results/v12_r6_dev_lifetime_lookup.json\`
- Refit: \`research/models/fit_recurrent_lookup.py\`
- Sampling: \`research/models/lifetime_paths.py\`
- Adapter: \`research/models/simulate_fitted_lifetime.py\`
- CI: \`.github/workflows/research-lifetime-tests.yml\`

To reproduce the fitted lookup without network or additional packages:

\`\`\`bash
python research/models/fit_recurrent_lookup.py \
  research/benchmarks/data/v12_r6_dev_lifetime_aggregates.json \
  /tmp/replayed-r6-lifetime.json
python research/models/simulate_fitted_lifetime.py \
  --model /tmp/replayed-r6-lifetime.json \
  --from-age 25 --to-age-exclusive 88 \
  --paths 200 --seed 20261008
\`\`\`

The simulator's example is a **mechanistic Monte Carlo demonstration using a trained retrospective DOCUMENTATION intensity**, not a reliable prediction of a real individual's lifetime.

## Next release blockers

1. Separate **true events vs their chance of being recorded**. A recording-propensity control has been added, but this is not an identified observation-process model.
2. Date uncertainty needs interval-censored likelihood rather than selection by dropping ambiguous annual windows.
3. A sequence/count model (possibly hurdle/negative-binomial and joint-domain dependence), better event types and state transitions should be compared on **fresh** validation/test people. No more optimizing against R4/R5 test people.
4. Temporal evaluation must use the actual **source publication revision available by cutoff**, not only event-date-based availability.
5. Long multi-step forecasts need person-cluster bootstrap, calibrated 3/5/10/20/40-year coverage, roll-out calibration and geography/era/occupation shifts.
6. Cohort is selectively notable and historical; never market it as representative of modern everyday life.
7. BaZi remains an unproven, off-by-default experimental prior.

**Decision:** Keep all training/validation and simulator assets in a Draft PR; no user-facing personalized forecast claims and no promotion to production until stronger empirical validation.
