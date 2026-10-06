# Final v1 benchmark — Round 1

Status: **completed / official corrected run**

This is the first model benchmark on the frozen `v1.0-final` training corpus. It is intentionally a simple sanity/incremental-signal test, not the final modeling result.

## Frozen experiment contract

- training dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- split scenario: `person_hash_v1`
- target: next documented canonical event, mapped to `career / recognition / relationship / other`
- classification rows: 7,465
- split rows: train 5,279 / validation 1,073 / test 1,113
- people with at least one observed classification target: 2,072
- seed: 20261006
- no hyperparameter search
- logistic model: `lbfgs`, C=1.0, max_iter=5000, class weights derived from train only
- test evaluated after the protocol was frozen
- paired confidence intervals use 1,000 bootstrap replicates clustered by person

Feature variants:

1. `history_reality_v1`
2. `raw_birth_calendar_v1`
3. `bazi_objective_only_v1`
4. `history_plus_bazi_v1`
5. `bazi_decade_shuffle_placebo_v1`

A train-prior majority baseline is also reported.

## Official artifact

Corrected workflow run: `37412032573`

GitHub Actions artifact:

- artifact ID: `11389687413`
- SHA-256: `e39ef02bd94cbab2d767d9c786679d48528b4317e85fbdccf12d3b9d822ba387`
- private Storage: `research-artifacts/model-runs/final-v1-round1/e39ef02bd94cbab2d767d9c786679d48528b4317e85fbdccf12d3b9d822ba387/bundle.zip`

The bundle contains the fitted logistic models, predictions, metrics, raw-domain diagnostics, model manifest, checksums, and summary.

Environment:

- Python 3.12.14
- NumPy 2.5.3
- pandas 2.3.3
- scikit-learn 1.9.1
- joblib 1.6.0

## Test results

| Model / features | Test N | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train-prior baseline | 1,113 | 0.1600 | 0.2500 | 1.2869 | 0.6928 | 0.0645 |
| History reality | 1,113 | **0.4138** | **0.4502** | **1.2435** | **0.6684** | **0.0585** |
| Raw birth calendar | 1,113 | 0.3324 | 0.3674 | 1.3443 | 0.7395 | 0.0845 |
| Objective BaZi | 1,113 | 0.2774 | 0.2966 | 1.7307 | 0.8843 | 0.2885 |
| History + BaZi | 1,113 | 0.3740 | 0.3969 | 1.5776 | 0.7988 | 0.2496 |
| Shuffled-BaZi placebo | 1,097 | 0.2608 | 0.2811 | 1.8200 | 0.9213 | 0.2974 |

The placebo has 16 fewer test rows because singleton birth-decade × split groups cannot satisfy a no-self donor derangement. These rows are excluded only from the placebo comparison.

## Validation sanity check

Macro-F1 is similar between validation and test:

| Features | Validation | Test |
| --- | ---: | ---: |
| History reality | 0.4200 | 0.4138 |
| Raw birth calendar | 0.3335 | 0.3324 |
| Objective BaZi | 0.2842 | 0.2774 |
| History + BaZi | 0.3935 | 0.3740 |
| Shuffled-BaZi placebo | 0.2218 | 0.2608 |

This reduces concern that the headline ordering is an isolated test-set fluctuation, although broader holdouts remain necessary.

## Paired person-cluster bootstrap

All deltas below are test macro-F1 differences. The resampling unit is person, not cutoff row.

| Comparison | Observed delta | 95% bootstrap CI | Positive bootstrap fraction |
| --- | ---: | ---: | ---: |
| History + BaZi − History | **−0.0398** | [−0.0891, +0.0095] | 0.058 |
| BaZi − Raw calendar | **−0.0550** | [−0.1118, +0.0042] | 0.030 |
| BaZi − Shuffled placebo | **+0.0139** | [−0.0487, +0.0701] | 0.661 |

Round 1 therefore does **not** provide statistically stable evidence that objective BaZi adds predictive value in this multinomial-logistic setting.

In particular:

- the true-BaZi versus matched-placebo delta is small and its interval crosses zero broadly;
- BaZi underperforms the raw birth/calendar baseline;
- adding BaZi to observed history decreases macro-F1 in the simple linear model.

This is a negative/null result for this model family, not evidence that every possible nonlinear or interaction-based BaZi representation has zero signal.

## Raw-domain diagnostic

The 4-class target pools many domains into `other`. To ensure that this does not hide the same ordering, raw-domain macro-F1 was also evaluated:

| Features | Raw-domain test macro-F1 |
| --- | ---: |
| History reality | **0.2034** |
| History + BaZi | 0.1666 |
| Raw birth calendar | 0.1380 |
| Objective BaZi | 0.1026 |
| Shuffled-BaZi placebo | 0.0896 |

The raw-domain diagnostic is consistent with the main 4-class result.

## What Round 1 establishes

The most useful signal in the current corpus is the person's documented pre-cutoff history. This is expected and validates the basic trajectory-learning premise: observed trajectory state contains information about the next documented event class.

Raw birth/calendar variables also outperform the prior baseline in macro-F1. Therefore future BaZi claims must be judged against this control, not merely against chance.

The objective BaZi feature vector performs only slightly better than its shuffled control and substantially worse than raw calendar features in a linear/logistic model. Its probability calibration is also poor (test ECE 0.2885), as is history+BaZi (0.2496), while history-only is much better calibrated (0.0585).

A plausible modeling explanation is that the engineered BaZi vector is high-dimensional and interaction-heavy, which a regularized linear multinomial model may represent poorly. That hypothesis must be tested prospectively with a frozen nonlinear protocol; it should not be assumed from these results.

## Preliminary artifact and metric correction

An earlier run produced artifact `11389063741`, SHA:

`e6e4da170a0496d8194be62e8a930197068aeb90f0e8bb6dd4d6c56e96ad5c8a`

scikit-learn 1.9 emitted a warning because the custom probability-column order supplied to `log_loss` was not lexicographic. Class predictions, macro-F1, balanced accuracy, Brier, ECE, fitted models, and bootstrap deltas were unaffected, but its log-loss values were not accepted as official.

That artifact is preserved in private Storage and explicitly registered as `superseded`. The corrected official run changed only the probability-class ordering used by metric evaluation; data, split, features, model hyperparameters, and seed remained unchanged.

## Database provenance

Six completed model runs are recorded in `research.model_runs`:

- majority/prior baseline
- history logistic
- raw-calendar logistic
- BaZi-only logistic
- history+BaZi logistic
- shuffled-BaZi logistic

Validation/test predictions are stored in `research.model_predictions`; metrics and bootstrap details are stored in `research.model_metrics`; artifact records point to the exact ZIP and inner model paths.

All Round 1 JSONB payloads were type-audited and normalized to real JSON objects rather than JSON-encoded strings.

## Next scientific step

Round 2 should test a nonlinear model under a protocol frozen **before** inspecting its test output.

The main questions are:

1. Can nonlinear interactions materially improve BaZi-only versus raw-calendar control?
2. Does history + BaZi add stable lift over history alone?
3. Does true BaZi separate from the matched shuffled-BaZi placebo?
4. Does any apparent lift survive forward-era and geography holdouts?
5. Does probability calibration remain acceptable?

No interpretation should be upgraded from “possible signal” to a useful predictive prior unless it survives these controls and out-of-domain holdouts.
