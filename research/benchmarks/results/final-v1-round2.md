# Final v1 benchmark — Round 2

Status: **completed / official nonlinear benchmark**

Round 2 was preregistered after Round 1 and before any Round 2 test evaluation. It asks whether nonlinear interactions materially change the Round 1 conclusion about objective BaZi features.

## Frozen experiment contract

- protocol: `next-canonical-domain-nonlinear-round2-v1`
- training dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- split: `person_hash_v1`
- target: `career / recognition / relationship / other`
- classification rows: 7,465
- split rows: train 5,279 / validation 1,073 / test 1,113
- model family: `HistGradientBoostingClassifier`
- seed: `20261006`
- balanced sample weights from training labels only
- early stopping disabled
- placebo excluded from model selection
- rejected candidate configurations were never evaluated on test

## Preregistered model selection

Three candidate capacities were allowed:

| Candidate | Learning rate | Iterations | Max leaves | Min leaf samples | L2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| hgb_small | 0.05 | 250 | 15 | 30 | 2.0 |
| hgb_medium | 0.05 | 350 | 31 | 25 | 4.0 |
| hgb_large | 0.04 | 450 | 63 | 20 | 8.0 |

Selection used only validation data. The score was mean validation macro-F1 across:

- history reality
- raw birth calendar
- objective BaZi
- history + BaZi

The shuffled-BaZi placebo did not participate.

Validation selection result:

| Candidate | Mean validation macro-F1 | Mean validation log loss |
| --- | ---: | ---: |
| **hgb_small** | **0.3759** | **1.3061** |
| hgb_large | 0.3695 | 1.4900 |
| hgb_medium | 0.3642 | 1.4064 |

Therefore `hgb_small` was selected and then used unchanged for all five final feature variants.

The fact that the smallest model won is itself useful: increasing nonlinear capacity did not improve average validation performance and worsened probability loss.

## Official artifact

Workflow run: `37413437609`

Artifact:

- artifact ID: `11390157851`
- SHA-256: `39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd`
- private Storage: `research-artifacts/model-runs/final-v1-round2/39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd/bundle.zip`

The ZIP SHA and all 12 internal file SHA-256 values were independently rechecked after download.

The artifact contains:

- validation candidate metrics
- model-selection record
- five fitted HGB models
- validation/test predictions
- classification metrics
- raw-domain diagnostics
- person-cluster bootstrap comparisons
- model manifest
- checksums

## Test results

| Features | Test N | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **History reality** | 1,113 | **0.4271** | **0.4589** | **1.2090** | 0.6609 | 0.1031 |
| Raw birth calendar | 1,113 | 0.3666 | 0.3859 | 1.3313 | 0.7317 | 0.1231 |
| Objective BaZi | 1,113 | 0.2728 | 0.2802 | 1.4531 | 0.7817 | 0.1696 |
| History + BaZi | 1,113 | 0.4238 | 0.4367 | 1.2201 | **0.6602** | **0.1025** |
| Shuffled-BaZi placebo | 1,097 | 0.2368 | 0.2405 | 1.5082 | 0.8064 | 0.1888 |

The placebo has 16 fewer test rows because singleton birth-decade × split groups cannot be assigned a non-self donor.

## Paired person-cluster bootstrap

All comparisons are test macro-F1 differences with 1,000 bootstrap replicates and person as the resampling unit.

| Comparison | Delta macro-F1 | 95% CI | Positive fraction |
| --- | ---: | ---: | ---: |
| History + BaZi − History | **−0.0033** | [−0.0446, +0.0391] | 0.417 |
| BaZi − Raw calendar | **−0.0939** | **[−0.1541, −0.0327]** | 0.000 |
| BaZi − Shuffled placebo | **+0.0382** | [−0.0152, +0.0896] | 0.919 |

These three comparisons answer the preregistered scientific gates:

1. **BaZi > raw calendar: fail.**  
   BaZi is substantially worse, and the full 95% bootstrap interval is below zero.

2. **BaZi > matched shuffled placebo: not established.**  
   The point estimate is positive and 91.9% of bootstrap replicates are positive, but the 95% interval still crosses zero.

3. **History + BaZi > history: fail / effectively null.**  
   The point estimate is almost exactly zero and the interval spans meaningful positive and negative effects.

Round 2 therefore does not overturn Round 1.

## Round 1 → Round 2

Macro-F1 comparison:

| Features | Logistic Round 1 | HGB Round 2 | Change |
| --- | ---: | ---: | ---: |
| History reality | 0.4138 | 0.4271 | +0.0133 |
| Raw birth calendar | 0.3324 | 0.3666 | +0.0342 |
| Objective BaZi | 0.2774 | 0.2728 | −0.0046 |
| History + BaZi | 0.3740 | 0.4238 | +0.0497 |
| Shuffled-BaZi placebo | 0.2608 | 0.2368 | −0.0241 |

Nonlinearity helps the trajectory/history representation and the raw calendar control. It does **not** improve BaZi-only performance.

History + BaZi improves strongly relative to its own linear Round 1 model, but that gain mostly allows it to recover toward the history-only model. It still does not exceed history alone.

This is an important distinction: nonlinear modeling can handle the enlarged combined feature space better, but the BaZi component has not demonstrated positive incremental value.

## Raw-domain diagnostic

The main target pools several domains into `other`. Raw-domain macro-F1 gives another check:

| Features | Raw-domain test macro-F1 |
| --- | ---: |
| **History reality** | **0.2315** |
| History + BaZi | 0.1944 |
| Raw birth calendar | 0.1708 |
| Shuffled-BaZi placebo | 0.1125 |
| Objective BaZi | 0.1039 |

The raw-domain diagnostic is even less favorable to a distinct BaZi signal: true BaZi is slightly below the shuffled placebo.

## Interpretation after two model families

Two different model families now tell a consistent story:

- pre-cutoff life history is the strongest available predictor of the next documented event class;
- raw birth/calendar variables contain measurable cohort or temporal signal and are a necessary control;
- the current objective BaZi representation does not beat that raw calendar control;
- true BaZi is somewhat above its matched placebo on the 4-class HGB task, but the uncertainty remains too large to establish stable incremental signal;
- adding BaZi to history does not improve held-out macro-F1 over history alone.

Therefore the current evidence supports the **life-trajectory modeling** part of MingGui much more strongly than the **BaZi incremental prior**.

This does not prove that every possible traditional feature construction has zero information. It does mean that any future BaZi claim must clear a higher evidentiary bar and cannot rely on the current objective feature set plus standard linear/nonlinear classifiers.

## Calibration

HGB improves BaZi calibration relative to Round 1 logistic:

- BaZi ECE: 0.2885 → 0.1696
- history + BaZi ECE: 0.2496 → 0.1025

But calibration improvement does not translate into predictive lift over the required controls.

History-only remains both strong and reasonably calibrated.

## Database provenance

Round 2 is materialized in the private research database as:

- 5 completed model runs
- 10,884 validation/test predictions
- 83 metric records
- 20 model-artifact references
- 12 validation model-selection trials

All run configs, environments, metric details, prediction probabilities, prediction metadata, artifact metadata, and selection-trial payloads were type-audited as real JSONB objects.

The first result-import invocation completed all substantive inserts but failed on a final metadata-update parameter type. No model was rerun. The metadata query was corrected, JSONB values normalized, and the one-time importer was returned to JWT-required mode.

## Next step

The next useful experiment is **not** another random model family on the same person-hash split.

Round 1 and Round 2 have already answered the basic capacity question. The stronger next test is out-of-domain robustness using the already-frozen split scenarios:

1. forward-era holdout
2. US geography holdout
3. France geography holdout

The primary model should remain the validation-selected `hgb_small` from Round 2; do not retune it on those holdouts.

That test asks whether the strong history signal generalizes across time and geography, and whether the small true-BaZi-versus-placebo difference survives outside the ordinary person-hash split.
