# Final v1 Round 3 preregistration

Frozen before holdout test evaluation.

- protocol: `next-canonical-domain-generalization-round3-v1`
- dataset: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- model: Round 2 `hgb_small`, unchanged
- seed: `20261006`
- no Round 3 hyperparameter selection
- validation is diagnostic only

Fixed holdouts:

- `forward_era_v1`
- `geo_us_holdout_v1`
- `geo_france_holdout_v1`

Fixed feature variants:

- history reality
- raw birth calendar
- objective BaZi
- history + BaZi
- scenario-matched shuffled-BaZi placebo

Every scenario fits preprocessing and balanced sample weights on its own training partition only. Test is evaluated once.

Primary metrics: macro-F1, balanced accuracy, multiclass log loss.
Calibration: multiclass Brier score and 10-bin ECE.
Diagnostic: raw-domain macro-F1.
Paired confidence intervals use 1,000 person-cluster bootstrap replicates.

Scientific gates remain fixed:

1. BaZi beats raw calendar.
2. True BaZi beats matched placebo.
3. History + BaZi beats history.

All three holdouts must be reported together; no favorable holdout may be selected after seeing results.
