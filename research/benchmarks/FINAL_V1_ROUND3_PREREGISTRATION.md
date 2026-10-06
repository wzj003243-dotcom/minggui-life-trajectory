# Final v1 Round 3 preregistration

Frozen before any Round 3 holdout evaluation.

## Purpose

Round 3 is an out-of-domain robustness test. It does not select or tune a new model.

The model configuration is fixed from Round 2:

- model family: `HistGradientBoostingClassifier`
- configuration: `hgb_small`
- learning rate: 0.05
- iterations: 250
- max leaves: 15
- min leaf samples: 30
- L2 regularization: 2.0
- early stopping: disabled
- seed: 20261006

No Round 3 validation or test result may alter these settings.

## Dataset and target

- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- target: `career / recognition / relationship / other`

Feature variants:

1. history reality
2. raw birth calendar
3. objective BaZi
4. history + BaZi
5. scenario-specific matched shuffled-BaZi placebo

## Holdout scenarios

### forward_era_v1

Observed classification rows:

- train: 3,171 rows / 862 people
- validation: 2,226 rows / 598 people
- test: 2,068 rows / 612 people

### geo_us_holdout_v1

- train: 3,557 rows / 985 people
- validation: 2,271 rows / 616 people
- test: 1,637 rows / 471 people

### geo_france_holdout_v1

- train: 3,557 rows / 985 people
- validation: 1,637 rows / 471 people
- test: 2,271 rows / 616 people

Geography semantics are the frozen split semantics already recorded in the training contract. They are not recomputed during Round 3.

## Weighting and preprocessing

For each scenario independently:

- balanced sample weights are computed from that scenario's train labels only;
- numeric imputation is fit on train only;
- categorical one-hot vocabulary is fit on train only;
- unknown validation/test categories are ignored;
- no validation-based hyperparameter tuning occurs.

## Metrics

For validation and test:

- macro-F1
- balanced accuracy
- multiclass log loss
- multiclass Brier score
- 10-bin ECE
- raw-domain macro-F1 diagnostic

Within each scenario, test comparisons use 1,000 paired bootstrap replicates clustered by person:

- history + BaZi minus history
- BaZi minus raw calendar
- BaZi minus scenario-specific shuffled placebo

## Scientific gates

Round 3 asks whether conclusions survive domain shift:

1. Does history remain stronger than raw calendar?
2. Does BaZi beat raw calendar?
3. Does true BaZi beat its matched placebo?
4. Does history + BaZi beat history?

No single scenario is allowed to redefine the model or feature construction.
