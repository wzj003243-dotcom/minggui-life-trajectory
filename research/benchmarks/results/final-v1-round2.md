# Final v1 benchmark — Round 2 nonlinear

Status: **completed / official**

Round 2 was preregistered before any Round 2 test evaluation. It tests whether a nonlinear tree model changes the Round 1 conclusion about incremental BaZi signal.

## Frozen protocol

- protocol: `next-canonical-domain-nonlinear-round2-v1`
- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- split: `person_hash_v1`
- target: `career / recognition / relationship / other`
- rows: 7,465
- people: 2,072
- split rows: train 5,279 / validation 1,073 / test 1,113
- seed: `20261006`

Model family:

`HistGradientBoostingClassifier`

Three candidate complexity levels were fixed in advance. Candidate selection used validation only, averaged across the four real feature variants. The shuffled placebo was excluded from selection. Rejected configurations were never evaluated on test.

## Validation-only model selection

| Candidate | Mean validation macro-F1 | Mean validation log loss |
| --- | ---: | ---: |
| **hgb_small** | **0.3759** | **1.3061** |
| hgb_large | 0.3695 | 1.4900 |
| hgb_medium | 0.3642 | 1.4064 |

Selected shared configuration:

- learning rate: 0.05
- iterations: 250
- max leaf nodes: 15
- min samples per leaf: 30
- L2 regularization: 2.0
- early stopping: false

The same selected configuration was used for all five feature variants.

## Official artifact

Workflow run: `37413437609`

Artifact:

- ID: `11390157851`
- SHA-256: `39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd`
- private Storage: `research-artifacts/model-runs/final-v1-round2/39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd/bundle.zip`

## Test results

| Features | Test N | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **History reality** | 1,113 | **0.4271** | **0.4589** | **1.2090** | 0.6609 | 0.1031 |
| Raw birth calendar | 1,113 | 0.3666 | 0.3859 | 1.3313 | 0.7317 | 0.1231 |
| Objective BaZi | 1,113 | 0.2728 | 0.2802 | 1.4531 | 0.7817 | 0.1696 |
| History + BaZi | 1,113 | 0.4238 | 0.4367 | 1.2201 | **0.6602** | **0.1025** |
| Shuffled-BaZi placebo | 1,097 | 0.2368 | 0.2405 | 1.5082 | 0.8064 | 0.1888 |

Validation and test remain directionally consistent:

| Features | Validation macro-F1 | Test macro-F1 |
| --- | ---: | ---: |
| History reality | 0.4437 | 0.4271 |
| Raw birth calendar | 0.3621 | 0.3666 |
| Objective BaZi | 0.2794 | 0.2728 |
| History + BaZi | 0.4184 | 0.4238 |
| Shuffled-BaZi placebo | 0.2453 | 0.2368 |

## Preregistered scientific gates

The three gates were:

1. BaZi > raw birth/calendar
2. true BaZi > matched shuffled-BaZi
3. history + BaZi > history

### Gate 1 — BaZi versus raw calendar

Observed test delta:

`BaZi - raw calendar = -0.0939 macro-F1`

Person-clustered 95% bootstrap CI:

`[-0.1541, -0.0327]`

Positive bootstrap fraction:

`0.000`

**Result: failed clearly.**

Under the selected nonlinear model, raw birth/calendar variables outperform the objective BaZi feature set by a large and statistically stable margin.

### Gate 2 — true BaZi versus shuffled placebo

Observed test delta:

`BaZi - placebo = +0.0382 macro-F1`

Person-clustered 95% bootstrap CI:

`[-0.0152, +0.0896]`

Positive bootstrap fraction:

`0.919`

**Result: suggestive but not passed.**

The nonlinear model increases the true-versus-placebo separation compared with Round 1, but the confidence interval still crosses zero. This is the only comparison in Round 2 that moves in the direction expected by a distinct BaZi signal.

### Gate 3 — history + BaZi versus history

Observed test delta:

`History + BaZi - History = -0.0033 macro-F1`

Person-clustered 95% bootstrap CI:

`[-0.0446, +0.0391]`

Positive bootstrap fraction:

`0.417`

**Result: failed / null.**

Adding BaZi to already-observed life history provides no detectable incremental classification lift in this model family.

## Raw-domain diagnostic

| Features | Raw-domain test macro-F1 |
| --- | ---: |
| **History reality** | **0.2315** |
| History + BaZi | 0.1944 |
| Raw birth calendar | 0.1708 |
| Shuffled-BaZi placebo | 0.1125 |
| Objective BaZi | 0.1039 |

The raw-domain diagnostic reinforces the main result. Objective BaZi does not outperform the matched placebo on this finer-grained target.

## Round 1 to Round 2

Nonlinearity improves the two strongest controls:

- history: 0.4138 → 0.4271
- raw calendar: 0.3324 → 0.3666

BaZi-only does not improve:

- BaZi: 0.2774 → 0.2728

History + BaZi improves relative to its Round 1 logistic version:

- 0.3740 → 0.4238

But it still does not beat history alone:

- history: 0.4271
- history + BaZi: 0.4238

The true-BaZi versus placebo gap becomes larger:

- Round 1: +0.0139
- Round 2: +0.0382

However, the Round 2 interval still includes zero.

## Interpretation

Round 2 does not support using objective BaZi as a demonstrated predictive prior yet.

The strongest evidence in the corpus remains:

1. observed pre-cutoff life history;
2. raw birth/calendar and demographic context;
3. only then the current BaZi representation.

A small possibility remains that true BaZi contains weak nonlinear structure not present in the matched shuffled control. The true-versus-placebo bootstrap is the one result worth continuing to monitor, but it is not strong enough to claim a reliable effect.

Most importantly, a distinct BaZi contribution should not be inferred merely because BaZi-only beats chance. It must beat its raw-calendar control and add information beyond history. Round 2 fails both requirements.

## Audit trail

Five completed Round 2 HGB runs are stored in `research.model_runs`.

The database contains:

- validation and test predictions;
- validation-only candidate-selection metrics;
- official validation/test metrics;
- person-cluster bootstrap details;
- fitted model artifact references;
- exact selection JSON;
- exact benchmark ZIP.

All imported config, environment, metric details, probabilities, prediction metadata, artifact metadata, and artifact-registry metadata were type-audited as JSONB objects.

The result importer is returned to JWT-required mode after import.

## Next step

The selected `hgb_small` model configuration is now frozen for generalization testing.

No further tuning should be performed before running:

1. forward-era holdout;
2. US geography holdout;
3. France geography holdout.

Those holdouts should answer whether history, raw-calendar, and any residual true-versus-placebo BaZi separation survive distribution shift.
