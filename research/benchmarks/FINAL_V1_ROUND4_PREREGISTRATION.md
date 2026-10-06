# Final v1 Round 4 preregistration

Frozen before any Round 4 test evaluation.

## Purpose

Rounds 1–3 show that pre-cutoff “history” is the strongest feature family and survives era/geography holdouts. However, the existing `history_reality_v1` representation mixes several information types:

- actual pre-cutoff event-domain content;
- static birth/demographic context;
- documentation/source-density signals.

Round 4 is a **shortcut ablation**. It does not search for a new model.

## Frozen dataset and model

- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- target: career / recognition / relationship / other
- model: Round-2 validation-selected `hgb_small`
- seed: `20261006`
- no Round 4 hyperparameter selection

Fixed HGB configuration:

- learning_rate = 0.05
- max_iter = 250
- max_leaf_nodes = 15
- min_samples_leaf = 30
- l2_regularization = 2.0
- early_stopping = false

Balanced sample weights are derived from each scenario's train partition only.

## Feature ablations

### history_reality_v1

Existing full history representation:

- cutoff age
- birth year
- gender
- birth country / geo group
- canonical and raw history counts
- domain count
- source-family count
- life-stage count
- per-domain event counts

### history_content_counts_v1

Retains pre-cutoff event content/count structure while removing static context and raw/source documentation controls:

- cutoff age
- canonical history event count
- domain count
- life-stage count
- per-domain event counts

Explicitly excludes:

- birth year
- gender
- country / geo group
- raw event count
- source-family count

### history_content_mix_v1

Aggressive density removal:

- cutoff age
- has-history indicator
- each domain's proportion of canonical history events

All static birth context and absolute history/source counts are excluded.

For a row with zero observed history, all domain proportions are zero and `has_history=0`.

### history_static_context_v1

Static shortcut control only:

- cutoff age
- birth year
- gender
- birth country
- birth geo group

No event-history variables.

### history_documentation_density_v1

Documentation-density control only:

- cutoff age
- canonical event count
- raw event count
- source-family count

No domain content, no static birth context, no BaZi.

## Scenarios

The exact same ablations are evaluated under:

1. `person_hash_v1`
2. `forward_era_v1`
3. `geo_us_holdout_v1`
4. `geo_france_holdout_v1`

No scenario is allowed to change model capacity or feature policy.

## Metrics

Primary:

- macro-F1
- balanced accuracy
- multiclass log loss

Calibration:

- multiclass Brier
- 10-bin ECE

Paired test comparisons use 1,000 bootstrap replicates clustered by person:

1. `history_content_counts - history_full`
2. `history_content_mix - static_context`
3. `history_content_counts - documentation_density`

## Interpretation

Round 4 is designed to answer:

> Does predictive power remain when static era/geography and documentation-density shortcuts are removed?

Evidence for event-content signal requires the history-content variants to remain meaningfully predictive and to outperform the static and/or documentation controls.

A strong `static_context` or `documentation_density` score is itself important evidence of dataset/source bias and must be reported, not hidden.

A strong `history_content_mix` score would be especially useful because it removes absolute history volume and therefore asks whether **what kinds of events have already happened**, rather than simply how richly a person is documented, predicts the next documented event class.

This benchmark does not establish causality and does not yet model event order/sequence.
