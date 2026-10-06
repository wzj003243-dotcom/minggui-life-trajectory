# Final v1 benchmark — Round 3

Status: **completed / official preregistered out-of-domain run**

Round 3 tested whether the trajectory signal found in the person-hash benchmark survives major cohort shifts. No Round 3 holdout was used for hyperparameter selection.

## Frozen protocol

- protocol: `next-canonical-domain-ood-round3-v1`
- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- model family: `HistGradientBoostingClassifier`
- fixed model: Round-2 validation-selected `hgb_small`
- no Round 3 hyperparameter selection
- balanced sample weights computed from each scenario's train partition only
- seed: `20261006`

Fixed configuration:

- learning rate: 0.05
- iterations: 250
- max leaf nodes: 15
- min samples per leaf: 30
- L2 regularization: 2.0
- early stopping: false

Holdouts:

1. `forward_era_v1`
2. `geo_us_holdout_v1`
3. `geo_france_holdout_v1`

All three scenarios contained all four target classes in train, validation, and test.

## Official artifact

Corrected successful workflow run: `37417426946`

- artifact ID: `11392340286`
- SHA-256: `5344a9c993602c29ced4c6453ccee4bd78f782046b2f08b1374619c2a451c293`
- size: 11,575,308 bytes
- private Storage:
  `research-artifacts/model-runs/final-v1-round3/5344a9c993602c29ced4c6453ccee4bd78f782046b2f08b1374619c2a451c293/bundle.zip`

Final database state:

- 15 completed model runs
- 60,452 validation/test predictions
- 45 model artifact records
- exact expected prediction count for every run
- exact expected metric count for every run
- all config/environment/metric/prediction/artifact JSONB payloads are proper JSON objects

## Test results

### Forward-era holdout

Test: 2,068 rows / 612 people.

| Features | Macro-F1 | Balanced acc. | Log loss |
| --- | ---: | ---: | ---: |
| **History reality** | **0.4022** | **0.4380** | **1.2568** |
| Raw birth calendar | 0.2854 | 0.2942 | 1.5297 |
| Objective BaZi | 0.2557 | 0.2582 | 1.5881 |
| History + BaZi | 0.3843 | 0.4140 | 1.3166 |
| Shuffled-BaZi placebo | 0.2344 | 0.2417 | 1.5458 |

Paired person-bootstrap macro-F1 deltas:

- History + BaZi − History: **−0.0179**, 95% CI [−0.0512, +0.0158]
- BaZi − Raw calendar: **−0.0297**, 95% CI [−0.0697, +0.0099]
- BaZi − placebo: **+0.0213**, 95% CI [−0.0160, +0.0628]

### US geography holdout

Test: 1,637 rows / 471 people.

| Features | Macro-F1 |
| --- | ---: |
| **History reality** | **0.4184** |
| Raw birth calendar | 0.2829 |
| Objective BaZi | 0.2598 |
| History + BaZi | 0.3702 |
| Shuffled-BaZi placebo | 0.2488 |

Paired person-bootstrap macro-F1 deltas:

- History + BaZi − History: **−0.0482**, 95% CI **[−0.0874, −0.0090]**
- BaZi − Raw calendar: **−0.0231**, 95% CI [−0.0702, +0.0245]
- BaZi − placebo: **+0.0115**, 95% CI [−0.0354, +0.0578]

The history + BaZi degradation is statistically stable in this holdout.

### France geography holdout

Test: 2,271 rows / 616 people.

| Features | Macro-F1 |
| --- | ---: |
| **History reality** | **0.3704** |
| Raw birth calendar | 0.2913 |
| Objective BaZi | 0.2844 |
| History + BaZi | 0.3542 |
| Shuffled-BaZi placebo | 0.2348 |

Paired person-bootstrap macro-F1 deltas:

- History + BaZi − History: **−0.0163**, 95% CI [−0.0465, +0.0138]
- BaZi − Raw calendar: **−0.0068**, 95% CI [−0.0445, +0.0321]
- BaZi − placebo: **+0.0482**, 95% CI **[+0.0092, +0.0852]**

France is the first holdout where true BaZi significantly beats the matched shuffled-BaZi placebo. This is a heterogeneous subgroup result, not evidence of a globally robust BaZi effect, because the same comparison is not significant in person-hash, forward-era, or US holdouts and BaZi still does not beat raw calendar in France.

## Raw-domain diagnostic

The same broad ordering survives the finer raw-domain task.

| Holdout | History | Raw calendar | BaZi | History + BaZi | Placebo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Forward era | **0.1893** | 0.1080 | 0.1007 | 0.1653 | 0.0826 |
| US | **0.2386** | 0.1349 | 0.1069 | 0.1619 | 0.1211 |
| France | **0.1932** | 0.1174 | 0.1104 | 0.1798 | 0.0968 |

## What Round 3 establishes

The strongest result is not about BaZi. It is that **pre-cutoff life history remains predictive under substantial era and geography shifts**.

History-only macro-F1:

- person-hash Round 2: 0.4271
- forward-era: 0.4022
- US holdout: 0.4184
- France holdout: 0.3704

The France drop shows that distribution shift matters, but the signal does not collapse toward the prior baseline. This is meaningful support for the central life-trajectory premise.

Across all three OOD holdouts:

- history remains the strongest feature family;
- adding BaZi never improves history macro-F1;
- BaZi never beats raw birth/calendar controls;
- true BaZi is directionally better than shuffled placebo in all three holdouts, but only France has a confidence interval wholly above zero.

The correct current scientific/product position is therefore:

> **History is the primary predictive engine. Raw birth/calendar is a real control and secondary predictor. Objective BaZi remains an experimental, low-confidence prior with heterogeneous but not robust incremental evidence.**

No deterministic fate claim is supported by these experiments.

## Import reliability note

The model workflow itself completed successfully and produced the frozen artifact above.

The first monolithic result importer later hit a Supabase Edge Function `WORKER_RESOURCE_LIMIT` while simultaneously holding the 11 MB ZIP and parsing roughly 60k predictions. This was a storage/import engineering failure, not a modeling failure.

Before the worker stopped, it had already archived the full ZIP and written all 15 model runs and all metrics. Predictions were partially written.

The missing predictions were then completed without rerunning any model:

1. the exact original `predictions.csv.gz` was verified by SHA;
2. it was deterministically partitioned into 15 scenario × feature-variant gzip chunks with fixed gzip `mtime=0`;
3. every chunk had a precomputed exact SHA and expected row count;
4. a SHA-allowlisted importer upserted each chunk idempotently;
5. final per-run prediction, metric, artifact, and JSONB-type audits all passed.

The temporary import/export endpoints were returned to JWT-required mode after use.

## Combined Round 1–3 conclusion

Three increasingly strict evaluations now agree:

1. multinomial logistic, person-hash;
2. nonlinear HGB, person-hash;
3. fixed nonlinear HGB under era and geography holdouts.

The stable ordering is:

[
	ext{Observed history} > 	ext{Raw birth/calendar control} > 	ext{Current objective BaZi representation}
]

The next scientific risk is that the current “history” feature family itself still includes static and coverage-related variables such as birth year, country/geo group, and source-density counts.

Therefore the next benchmark should not search for another model. It should **ablate history shortcuts** and test whether trajectory content itself drives the signal.
