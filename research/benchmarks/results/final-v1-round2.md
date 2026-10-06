# Final v1 benchmark — Round 2

Status: **completed / official preregistered nonlinear run**

Round 2 tested whether a nonlinear tree model changes the Round 1 conclusion about objective BaZi features.

## Preregistered protocol

The protocol was frozen before any Round 2 test evaluation:

- protocol: `next-canonical-domain-nonlinear-round2-v1`
- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- split: `person_hash_v1`
- model family: `HistGradientBoostingClassifier`
- seed: `20261006`
- balanced sample weights from train only
- placebo excluded from hyperparameter selection
- rejected hyperparameter candidates never evaluated on test
- one shared selected configuration used for all five feature variants

Preregistration file:

`research/benchmarks/FINAL_V1_ROUND2_PREREGISTRATION.md`

## Validation-only model selection

Three configurations were eligible.

| Candidate | Mean validation macro-F1 | Mean validation log loss |
| --- | ---: | ---: |
| **hgb_small** | **0.3759** | **1.3061** |
| hgb_large | 0.3695 | 1.4900 |
| hgb_medium | 0.3642 | 1.4064 |

The preregistered selection rule therefore chose `hgb_small`:

- learning rate: 0.05
- iterations: 250
- max leaf nodes: 15
- min samples per leaf: 30
- L2 regularization: 2.0
- early stopping: false

No rejected candidate was evaluated on test.

## Official artifact

Workflow run: `37413437609`

Artifact:

- artifact ID: `11390157851`
- SHA-256: `39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd`
- private Storage: `research-artifacts/model-runs/final-v1-round2/39337ab164b62a7301eae7c7ca260d48065751f7bcad482efd2c552d80ed46bd/bundle.zip`

The artifact contains:

- validation candidate-selection evidence
- selected configuration
- five fitted HGB models
- validation/test predictions
- 4-class metrics
- raw-domain diagnostics
- paired person-bootstrap comparisons
- model manifest and exact checksums

## Test results

| Features | Test N | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **History reality** | 1,113 | **0.4271** | **0.4589** | **1.2090** | 0.6609 | 0.1031 |
| Raw birth calendar | 1,113 | 0.3666 | 0.3859 | 1.3313 | 0.7317 | 0.1231 |
| Objective BaZi | 1,113 | 0.2728 | 0.2802 | 1.4531 | 0.7817 | 0.1696 |
| History + BaZi | 1,113 | 0.4238 | 0.4367 | 1.2201 | **0.6602** | **0.1025** |
| Shuffled-BaZi placebo | 1,097 | 0.2368 | 0.2405 | 1.5082 | 0.8064 | 0.1888 |

The nonlinear model improves history-only macro-F1 from Round 1 logistic `0.4138` to `0.4271`.

Raw calendar also improves from `0.3324` to `0.3666`.

Objective BaZi does not improve over its Round 1 logistic result; its test macro-F1 is `0.2728` versus `0.2774` in Round 1.

## Preregistered scientific gates

All deltas are paired test macro-F1 differences with 1,000 bootstrap replicates clustered by person.

| Gate | Delta | 95% CI | Result |
| --- | ---: | ---: | --- |
| History + BaZi − History | −0.0033 | [−0.0446, +0.0391] | **not passed** |
| BaZi − Raw calendar | −0.0939 | [−0.1541, −0.0327] | **failed clearly** |
| BaZi − Shuffled placebo | +0.0382 | [−0.0152, +0.0896] | **not passed** |

The second result is especially informative: all 1,000 person-cluster bootstrap replicates had BaZi below raw calendar (`positive_fraction = 0.0`).

True BaZi is directionally better than the matched shuffled placebo, with a positive bootstrap fraction of `0.919`, but the 95% interval still crosses zero. This is not sufficient evidence for an incremental BaZi effect under the frozen protocol.

## Raw-domain diagnostic

| Features | Raw-domain test macro-F1 |
| --- | ---: |
| **History reality** | **0.2315** |
| History + BaZi | 0.1944 |
| Raw birth calendar | 0.1708 |
| Shuffled-BaZi placebo | 0.1125 |
| Objective BaZi | 0.1039 |

The raw-domain diagnostic makes the same substantive point as the 4-class task.

## Combined interpretation of Round 1 and Round 2

Two different model families now agree on the core ordering:

[
	ext{History} > 	ext{Raw birth/calendar} > 	ext{Objective BaZi}
]

Round 1 used multinomial logistic regression.

Round 2 used a preregistered nonlinear gradient-boosted tree model selected on validation only.

The nonlinear model materially helps the history and raw-calendar representations, but it does not reveal a hidden objective-BaZi advantage.

At this point, the evidence supports:

1. **Observed life history is the strongest current signal for predicting the next documented event class.**
2. **Birth/calendar variables carry measurable predictive information and therefore are a necessary control.**
3. **The current objective BaZi representation has not demonstrated stable incremental predictive value over raw calendar or observed history.**
4. **True BaZi is somewhat better than a matched shuffled-BaZi placebo in both Round 1 and Round 2, but neither comparison is statistically stable.**

The correct product/scientific interpretation is therefore to keep BaZi as a **low-confidence prior / experimental feature**, not as a dominant deterministic mechanism.

## Database provenance

Five completed Round 2 model runs are stored in `research.model_runs`:

- HGB history reality
- HGB raw birth calendar
- HGB objective BaZi
- HGB history + BaZi
- HGB shuffled-BaZi placebo

Their validation/test predictions are stored in `research.model_predictions`, metrics and bootstrap intervals in `research.model_metrics`, and artifact records in `research.model_artifacts`.

All run configs and environments are proper JSONB objects.

## Next step

The next modeling question is no longer “can another flexible model rescue BaZi on the same random person split?”

The more valuable question is whether the strongest trajectory signal generalizes out of distribution.

Next benchmark should freeze the selected `hgb_small` capacity and evaluate:

1. forward-era holdout;
2. US geography holdout;
3. France geography holdout.

No additional hyperparameter selection should use those holdouts.

The purpose is to distinguish durable trajectory structure from cohort/source/geography shortcuts.
