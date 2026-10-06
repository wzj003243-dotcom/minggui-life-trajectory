# Final v1 Round 4 preregistration — censor-aware trajectory

Frozen before Round 4 test evaluation.

## Derived dataset

- dataset: `next-canonical-event-discrete-hazard / v1.0-derived`
- dataset ID: `731fa601-9c18-4ce8-9a8a-557ded47395d`
- fingerprint: `9e2de5961856ad79ae260cb87fea1028f38b278c74eb3ff7669d94a35cf9f7c3`
- source dataset: frozen final-v1 classification/censor-aware dataset
- source fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- cutoff states used: 13,064
- people: 3,382
- person-period rows: 52,427
- event rows within 20 years: 6,060
- event-free risk rows: 46,367

No source row was deleted or mutated. Partial censor intervals do not receive false no-event labels.

## Time grid

Finite horizon: 20 years.

Intervals:

1. 0–1 year
2. 1–3 years
3. 3–5 years
4. 5–10 years
5. 10–20 years

Outcomes per at-risk interval:

- no_event
- career
- recognition
- relationship
- other

The risk set stops after the first documented canonical target.

## Split

Use the frozen `person_hash_v1` person split. A person never crosses partitions.

Round 4 performs no hyperparameter search.

## Models

1. interval empirical prior by interval index
2. multinomial logistic regression, C=1, max_iter=5000, no class weights
3. frozen `hgb_small` capacity:
   - learning rate 0.05
   - iterations 250
   - max leaf nodes 15
   - min leaf samples 30
   - L2 2.0
   - early stopping disabled

Primary probability models use no class balancing because class balancing would intentionally alter the empirical hazard distribution and degrade probability interpretation.

## Feature variants

- history reality
- raw birth calendar
- objective BaZi
- history + BaZi
- matched shuffled-BaZi placebo

Only interval timing variables are added to the frozen cutoff feature snapshot:

- interval index
- interval start year
- interval end year
- interval width

## Primary interval metrics

- multiclass log loss
- multiclass Brier score
- ECE
- event-vs-no-event Brier score

Secondary:

- accuracy
- balanced accuracy
- macro-F1
- conditional event-domain log loss and macro-F1 among observed event rows

## Cumulative trajectory diagnostics

Compose interval hazards into cumulative incidence at:

- 1 year
- 3 years
- 5 years
- 10 years
- 20 years

For a horizon metric, exclude only cutoff states whose observation ends before the horizon with no known later target. A known later first target proves the preceding horizon event-free.

## Feature-comparison uncertainty

On test predictions, use 1,000 person-cluster bootstrap replicates for:

- history + BaZi versus history
- BaZi versus raw calendar
- true BaZi versus matched shuffled placebo

Primary paired deltas are interval multiclass log loss and Brier score. Negative delta favors the first-named variant.

## Interpretation

This round asks whether the system can produce calibrated probabilistic trajectories while respecting right censoring.

It does not redefine the documented-event target as ground-truth destiny. BaZi remains experimental unless it adds stable probabilistic value beyond history/raw-calendar controls.
