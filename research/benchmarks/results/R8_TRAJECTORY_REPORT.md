# R8 — From annual models to observable multi-stage trajectories

**Status:** implemented, reproducible and dev-validated; **not scientifically validated for personal fate predictions**.  
**Date:** October 15, 2026.  
**Based on:** frozen v1.1 `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02` historical biographies.

## What genuinely changed

Prior public experience showed preset descriptions for three possible future choices, which can be useful for reflection but **did not originate from a fitted time-series model**. R8 adds a separate, **real frozen R6 rate-based** multi-stage Monte Carlo engine and shows its historical cohort pathways in the user-facing report. The output is visually distinct from personal narration and traditional BaZi.

Implementation:
- `lib/historical-trajectory.ts`: deterministic seeded Poisson event simulation, annual age-only rates, stagewise 5-year expected documented-event counts, sample trajectory events, count p10/median/p90.
- `components/HistoricalTrajectoryPanel.tsx`: 5/10/20-year selectable horizon, 4 archival event domains, stage bars, sample paths and explicit non-personal scope.
- `components/Analyzer.tsx`: embeds research experiment within readable life report when ages 18–87.
- `tests/historical-trajectory.test.ts`: exact analytic expected values, deterministic seed, input limits, out-of-sample age cutoff.
- Frozen R6 model: `research/benchmarks/results/v12_r6_dev_lifetime_lookup.json`.

Critically the new path engine does **NOT** put self-reported events into `age_history_rates`. Public questionnaire event counts and frozen archival canonical-event counts are **different measurement mechanisms**; mapping the first to the second without validation would create plausible-looking but spurious personalized predictions. The model is deliberately age-only.

## What the R6 cohort rates would produce

Example research calculation **starting age 28** (NOT a forecast for a particular 28-year-old):

| Horizon | Model expected canonical biography entries |
| --- | ---: |
| Ages 28–32 (5 years) | 0.213 |
| Ages 28–37 (10 years) | 0.426 |
| Ages 28–47 (20 years) | 0.994 |

These small numbers do **not** mean people's actual lives have hardly any events. They mean a non-representative historical sample has a sparse, selective canonical-event recording process. The category `other` includes prolific publications/creative releases, not just life-state transitions.

The engine has not been calibrated for joint multi-year path distributions or individual people's possible life transitions. It is not a survival/mortality model; one simulated year in this code is not a chance that someone lives through that year.

## New stagewise calibration stress test

`research/benchmarks/audit_r8_stagewise_calibration.py` replays age-only TRAIN-derived annual archival count expectations against existing VALIDATION **age-bin aggregates**. Already inspected development validation: **21,449 validation person-years**; not an untouched external cohort. This is an **age-stratified annual count audit**, NOT a multiyear individual path validation.

Predefined internal descriptive mismatch flags at expected count ≥5 and observed/expected below 0.5 or above 2.0:

| Validation age band | Domain | Observed records | Model expected | Observed / expected |
| --- | --- | ---: | ---: | ---: |
| 48–57 | other | 37 | ~99.2 | 0.37 |
| 58–67 | other | 162 | ~72.7 | 2.23 |
| 78–87 | other | 3 | ~23.4 | 0.13 |

**Three flags total.** These thresholds are diagnostic engineering safeguards, not statistical confidence limits or a significance test. Because per-person contribution is heterogeneous, treating 21,449 person-years as independent would produce misleadingly narrow certainty intervals.

The result artifact `research/benchmarks/results/r8_stage_calibration_audit.json` fixes:
- `ready_for_personal_life_forecast = false`
- `is_multi_year_trajectory_calibrated = false`
- `audit_not_fresh_external_holdout = true`

## Model validity boundaries

1. R6 labels are retrospective biographies of famous/selected people, not comprehensive modern individual event registries.
2. Source visibility, censoring and era/geography/occupation confounding have not been removed.
3. The event ontology has large repeated-creation/output components; calling them all meaningful life transitions is wrong.
4. Poisson assumes independent counts across domains/years conditional on age; clustering, burstiness and heavy tails are poorly modeled.
5. Long-range age-only rollout is not heldout-validated; the Monte Carlo spread is **sampling variation conditional on the model**, not uncertainty about whether the model works in reality.
6. Full person-specific history features and BaZi are held out of this public demo, not granted arbitrary statistical weight.
7. A sampled path event is an illustration of a **record category** at an age, not a specific life event or predicted date. The sample visualizer does not invent marriages, promotions, illnesses or deaths.
8. Do not report probability of any life change, mortality, wealth, health, marriage or career outcome based on this engine.

## Research milestones that must precede actual fortune probabilities

- Retrain on **life-state transition** labels separated from repeated creations; preserve all raw event facts and provenance in sidecar tables.
- Create cutoff-replayable individual longitudinal validation with explicit missing-document observations and person-cluster confidence bands. Fix multiple event-date precision.
- Validate 5-, 10- and 20-year **joint distribution** calibration, not just annual binary log-loss.
- Acquire truly fresh person-disjoint and time/region-diverse external data. Earlier R4/R5 test persons have been inspected and should not be claimed untouched.
- Evaluate classical BaZi × DaYun × annual signs only as preregistered feature families against matched calendar and shifted-cycle controls. Current R7B did not show gain.
- Only then publish carefully calibrated, timestamped probabilities for actual, verifiable *future* outcomes, with an immutable prediction ledger.

**Bottom line:** R8 is a genuine data-fitted and reproducible life-path *research visualization*, but it explicitly does not claim personal life forecasting accuracy. This preserves both the user's whole-life product ambition and defensible scientific methodology.
