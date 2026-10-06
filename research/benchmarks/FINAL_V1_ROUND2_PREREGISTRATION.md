# Final v1 Round 2 preregistration

Frozen before any Round 2 test evaluation.

## Dataset and target

- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- split: `person_hash_v1`
- target: `career / recognition / relationship / other`
- seed: `20261006`

## Question

Round 1 showed no stable incremental BaZi signal in a multinomial-logistic model. Round 2 asks whether a nonlinear tree model changes that conclusion.

A higher score is not sufficient by itself. The scientific gates are:

1. `bazi_objective_only_v1 > raw_birth_calendar_v1`
2. `bazi_objective_only_v1 > bazi_decade_shuffle_placebo_v1`
3. `history_plus_bazi_v1 > history_reality_v1`

All three comparisons are evaluated with person-clustered paired bootstrap intervals.

## Model family

`HistGradientBoostingClassifier`

Preprocessing:

- numeric: median imputation, no scaling
- categorical: constant missing token followed by dense one-hot encoding
- encoder fit on training data only
- unknown validation/test categories ignored
- early stopping disabled
- balanced sample weights computed from training labels only

## Candidate configurations

Exactly three configurations are eligible:

| Key | learning rate | iterations | max leaves | min leaf samples | L2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| hgb_small | 0.05 | 250 | 15 | 30 | 2.0 |
| hgb_medium | 0.05 | 350 | 31 | 25 | 4.0 |
| hgb_large | 0.04 | 450 | 63 | 20 | 8.0 |

## Selection rule

Test is not used during selection.

For each candidate, compute validation macro-F1 on these four real feature variants:

- history reality
- raw birth calendar
- objective BaZi only
- history + BaZi

The shuffled-BaZi placebo is excluded from model selection.

Select exactly one shared configuration using:

1. highest mean validation macro-F1 across the four real variants;
2. if tied, lower mean validation log loss;
3. if still tied, lower complexity order: small, medium, large.

After selection, the same selected hyperparameters are used for all five feature variants. Rejected candidates are never evaluated on test.

## Test metrics

Primary:

- macro-F1
- balanced accuracy
- multiclass log loss

Calibration:

- multiclass Brier score
- 10-bin expected calibration error

Diagnostic:

- raw-domain macro-F1

Comparisons:

- history + BaZi minus history
- BaZi minus raw calendar
- BaZi minus matched shuffled-BaZi placebo

Confidence intervals use 1,000 paired bootstrap replicates, with person as the resampling unit so multiple cutoff rows for one person remain clustered.

## Interpretation

Round 2 can overturn the Round 1 linear-model conclusion only if nonlinear BaZi signal survives its controls.

If true BaZi improves overall score but fails to beat raw calendar or matched placebo, it is not treated as evidence of a distinct BaZi contribution.

If history + BaZi fails to beat history alone, BaZi is not treated as adding useful incremental trajectory information in this model family.

Forward-era and geography holdouts remain later tests and are not part of Round 2 model selection.
