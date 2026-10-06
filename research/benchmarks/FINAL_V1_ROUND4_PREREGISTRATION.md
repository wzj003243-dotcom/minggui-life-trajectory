# Final v1 Round 4 preregistration — discrete trajectory hazard

Frozen before Round 4 test evaluation.

## Dataset

- dataset: `next-canonical-event-discrete-hazard / v1.0-derived`
- dataset ID: `731fa601-9c18-4ce8-9a8a-557ded47395d`
- fingerprint: `9e2de5961856ad79ae260cb87fea1028f38b278c74eb3ff7669d94a35cf9f7c3`
- source final-v1 dataset remains immutable
- observation policy: `trajectory-observation-v1`

Risk intervals:

- (0, 1] years
- (1, 3] years
- (3, 5] years
- (5, 10] years
- (10, 20] years

Outcome per at-risk interval:

- no_event
- career
- recognition
- relationship
- other

Partial censor intervals do not receive labels.

## Models

No hyperparameter search.

1. interval-specific empirical train prior
2. unweighted multinomial logistic regression, C=1.0
3. frozen `hgb_small` capacity from Round 2:
   - learning_rate 0.05
   - max_iter 250
   - max_leaf_nodes 15
   - min_samples_leaf 30
   - l2_regularization 2.0
   - early_stopping false

No class balancing is used in Round 4 because the goal is calibrated hazard probability rather than balanced classification score.

## Features

Every model receives interval timing variables:

- interval_index
- interval_start_year
- interval_end_year
- interval_width_years

Feature ablations:

- history reality
- raw birth calendar
- objective BaZi
- history + BaZi
- matched shuffled-BaZi placebo

All non-time features come from the already-frozen cutoff feature snapshot.

## Split

Initial benchmark uses `person_hash_v1`.

People do not cross train / validation / test.

## Primary evaluation

Interval-level likelihood is primary because the frozen risk-set construction already handles right censoring.

Primary:

- multiclass log loss
- multiclass Brier score
- calibration error
- event-vs-no-event Brier score

Event-domain diagnostics on observed event intervals:

- conditional domain log loss
- conditional domain macro-F1

Secondary:

- accuracy
- macro-F1
- balanced accuracy

## Horizon diagnostics

Conditional interval probabilities are chained into cumulative incidence at:

- 1 year
- 3 years
- 5 years
- 10 years
- 20 years

For each horizon, evaluate the five-state distribution:

- no event by horizon
- career first event
- recognition first event
- relationship first event
- other first event

Horizon scores use only cutoff states whose outcome is fully known at that horizon. They are diagnostic; interval likelihood remains the primary censor-aware score.

## Interpretation

Round 4 asks whether the system can produce a useful probabilistic future trajectory, not whether BaZi can win a standalone benchmark.

History is expected to be the dominant state information. Raw calendar and BaZi remain explicitly separated so any prior contribution can be audited rather than hidden inside one model.
