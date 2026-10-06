# Final v1 benchmark — Round 4 censor-aware trajectory

Status: **completed / official**

Round 4 is the first benchmark that models both **when** the next documented canonical event occurs and **what kind** of event it is, while respecting right censoring.

## Frozen data contract

- protocol: `discrete-hazard-trajectory-round4-v1`
- trajectory dataset ID: `731fa601-9c18-4ce8-9a8a-557ded47395d`
- trajectory fingerprint: `9e2de5961856ad79ae260cb87fea1028f38b278c74eb3ff7669d94a35cf9f7c3`
- source final-v1 dataset: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- source fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- cutoff states: 13,064
- people: 3,382
- person-period rows: 52,427
- event rows within 20 years: 6,060
- event-free risk rows: 46,367
- intervals: 0–1, 1–3, 3–5, 5–10, 10–20 years
- split: frozen `person_hash_v1`
- no Round 4 hyperparameter search
- no class balancing in the primary probability models

The derivation was independently replayed from frozen source rows and reproduced exactly:

- 52,427 person-period rows
- 6,060 event rows
- 13,064 cutoff states
- 3,382 people

Partial censor intervals are absent from the likelihood rather than being labeled no-event. Five historical people with missing death facts and implausible administrative exposure through 2026 are excluded from hazard fitting only; their source records remain preserved.

## Models

1. empirical interval prior
2. multinomial logistic regression
3. frozen `hgb_small` HistGradientBoosting

Feature variants:

- history reality
- raw birth calendar
- objective BaZi
- history + BaZi
- matched shuffled-BaZi placebo

## Official artifact

Workflow run: `37426861843`

Artifact:

- ID: `11395666323`
- SHA-256: `750dd5f4613cebe599cde9964cb1a3ca46ee42d7fea4f474b6e8aa3bcf20290f`
- private Storage: `research-artifacts/model-runs/final-v1-round4/750dd5f4613cebe599cde9964cb1a3ca46ee42d7fea4f474b6e8aa3bcf20290f/bundle.zip`

The bundle contains all fitted models, interval predictions, cumulative-horizon predictions, metrics, manifests, and checksums.

## Interval-level test probability results

Because 89% of test person-period rows are event-free, accuracy alone is not informative. The primary comparison is probability quality.

| Model / features | Log loss ↓ | Multiclass Brier ↓ | Event/no-event Brier ↓ | ECE ↓ | Conditional event-domain log loss ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Interval prior | 0.4758 | 0.2017 | 0.0961 | 0.0082 | 1.2505 |
| Logistic — History | 0.4216 | 0.1856 | 0.0867 | 0.0081 | 1.1015 |
| Logistic — Raw calendar | 0.4661 | 0.1999 | 0.0950 | **0.0060** | 1.2030 |
| Logistic — BaZi | 0.5402 | 0.2189 | 0.1055 | 0.0491 | 1.5604 |
| Logistic — History + BaZi | 0.4739 | 0.1979 | 0.0920 | 0.0176 | 1.3953 |
| Logistic — shuffled BaZi | 0.5318 | 0.2130 | 0.1019 | 0.0447 | 1.5813 |
| **HGB — History** | **0.4059** | **0.1824** | **0.0855** | 0.0064 | **0.9969** |
| HGB — Raw calendar | 0.4674 | 0.2025 | 0.0964 | 0.0118 | 1.2049 |
| HGB — BaZi | 0.4985 | 0.2075 | 0.0994 | 0.0355 | 1.3451 |
| HGB — History + BaZi | 0.4226 | 0.1867 | 0.0877 | 0.0131 | 1.0727 |
| HGB — shuffled BaZi | 0.4940 | 0.2047 | 0.0978 | 0.0302 | 1.3639 |

HGB history reduces test interval log loss by about **14.7%** relative to the empirical interval prior and reduces multiclass Brier by about **9.5%**.

This is the strongest evidence so far that documented pre-cutoff life history carries usable probabilistic trajectory information.

## Person-clustered paired bootstrap

Negative delta favors the first-named model.

### HGB

| Comparison | Δ log loss | 95% CI | Δ Brier | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| History + BaZi − History | **+0.0167** | [+0.0096, +0.0243] | **+0.00423** | [+0.00169, +0.00682] |
| BaZi − Raw calendar | **+0.0310** | [+0.0194, +0.0429] | **+0.00504** | [+0.00145, +0.00870] |
| BaZi − shuffled placebo | +0.00126 | [−0.0108, +0.0127] | +0.00159 | [−0.00144, +0.00464] |

### Logistic

| Comparison | Δ log loss | 95% CI | Δ Brier | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| History + BaZi − History | **+0.0523** | [+0.0415, +0.0640] | **+0.0123** | [+0.00944, +0.0153] |
| BaZi − Raw calendar | **+0.0741** | [+0.0588, +0.0906] | **+0.0190** | [+0.0139, +0.0245] |
| BaZi − shuffled placebo | +0.00498 | [−0.0135, +0.0247] | +0.00474 | [−0.00135, +0.0116] |

Round 4 therefore makes the BaZi conclusion more decisive:

- adding BaZi to history significantly worsens probability quality;
- BaZi is significantly worse than the raw birth-calendar control;
- true BaZi and the matched shuffled-BaZi placebo are statistically indistinguishable.

The small true-versus-placebo differences seen in some earlier classification splits do not survive as a reliable probabilistic hazard contribution.

## Cumulative trajectory probabilities

Interval hazards were composed into cumulative incidence at 1, 3, 5, 10, and 20 years.

For HGB history-only, test log loss is:

| Horizon | Log loss | Brier | Event/no-event Brier | Macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| 1 year | **0.2457** | **0.1118** | **0.0526** | 0.3528 |
| 3 years | **0.4740** | **0.2206** | **0.0996** | 0.3697 |
| 5 years | **0.6134** | **0.2917** | **0.1260** | 0.3868 |
| 10 years | **0.8261** | **0.4105** | **0.1671** | 0.3880 |
| 20 years | **1.0686** | **0.5430** | **0.2001** | 0.3879 |

The absolute loss naturally rises with horizon because more events accumulate and the multi-class future becomes less certain; values should be compared **within a horizon**, not across horizons.

History-only beats history+BaZi at every listed horizon on log loss.

## Artifact integrity

The Round 4 artifact was audited before import:

- interval predictions: 178,868
- cumulative-horizon predictions: 221,080
- duplicate prediction keys: 0
- maximum probability-sum error: < 7e-16
- invalid negative probabilities: 0
- non-monotone survival curves: 0
- evaluable horizon rows with missing truth: 0
- non-evaluable rows with fabricated truth: 0

Database import is complete and verified:

- model runs: 11
- interval predictions: 178,868
- horizon predictions: 221,080
- model metrics: 1,464
- model artifacts: 33
- malformed JSONB payloads: 0

The exact ZIP is archived in private Storage. The one-off importer is returned to JWT-required mode.

## Scientific conclusion after Rounds 1–4

The product now has a defensible probabilistic core:

> **Observed life history predicts the distribution and timing of the next documented life event better than interval priors, raw birth-calendar controls, or the current BaZi representation.**

The strongest current model is nonlinear history-only.

BaZi should remain available only as an explicitly experimental, low-confidence auxiliary prior. The current v1.0 evidence does not justify giving it positive model weight by default.

Further tuning against the frozen v1.0 tests should stop. Improvement should now come from:

1. new v1.1 source coverage;
2. richer event representation;
3. broader cohorts;
4. sequence/time-varying trajectory models trained on a new frozen benchmark.

That keeps v1.0 as a genuine out-of-sample scientific benchmark rather than gradually fitting to it.
