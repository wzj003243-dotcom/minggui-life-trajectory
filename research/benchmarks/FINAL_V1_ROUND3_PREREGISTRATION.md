# Final v1 Round 3 preregistration

Frozen before any Round 3 holdout evaluation.

## Purpose

Round 3 tests out-of-domain generalization. No Round 3 holdout is used for model or hyperparameter selection.

## Fixed model

Round 2 selected `hgb_small` using validation only. Round 3 reuses it unchanged:

- HistGradientBoostingClassifier
- learning_rate = 0.05
- max_iter = 250
- max_leaf_nodes = 15
- min_samples_leaf = 30
- l2_regularization = 2.0
- early_stopping = false
- random seed = 20261006

Preprocessing is unchanged:

- numeric median imputation
- categorical constant-missing imputation + dense one-hot
- encoders fit on scenario train only
- unknown validation/test categories ignored
- balanced sample weights derived from scenario train labels only

## Frozen dataset

- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- target: career / recognition / relationship / other
- feature variants:
  - history reality
  - raw birth calendar
  - objective BaZi
  - history + BaZi
  - matched shuffled-BaZi placebo

## Holdouts

Exactly three split scenarios are evaluated:

1. `forward_era_v1`
2. `geo_us_holdout_v1`
3. `geo_france_holdout_v1`

Every scenario contains all four target classes in train, validation, and test.

Observed test sizes before modeling:

- forward era: 2,068 rows
- US holdout: 1,637 rows
- France holdout: 2,271 rows

These support counts are structural checks only and cannot be used to modify the model.

## Metrics

Primary:

- macro-F1
- balanced accuracy
- multiclass log loss

Calibration:

- multiclass Brier
- 10-bin ECE

Diagnostic:

- raw-domain macro-F1

Within each holdout, three paired comparisons are reported using 1,000 bootstrap replicates clustered by person:

- history + BaZi minus history
- BaZi minus raw calendar
- BaZi minus matched shuffled placebo

## Interpretation

No scenario-specific tuning is allowed.

The most important Round 3 question is whether history-based trajectory signal remains useful under time/geography shift.

BaZi is considered to provide incremental evidence only if true BaZi beats its raw-calendar control and matched placebo, and history + BaZi improves over history alone.

A result that succeeds only on the person-hash split but collapses under holdout is treated as evidence of cohort/source shortcut rather than durable life-trajectory structure.
