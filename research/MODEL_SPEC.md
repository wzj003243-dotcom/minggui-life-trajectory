# Model Spec v0.1

## Prediction unit
A person at information cutoff age `t`. All features must be observable at or before `t`.

## Core targets

### A. Lifetime archetype (multi-label)
- exploratory-reconstruction
- institutional-ascent
- stable-specialist
- creative-influence
- system-builder
- entrepreneurial-volatility
- research-scholar
- migration-heavy
- late-blooming

Archetypes are not moral rankings and may co-exist.

### B. Event windows (competing risks / hazard)
Predict probability within age windows for:
- major education transition
- cross-region / cross-country migration
- major career-domain switch
- first substantial public recognition
- leadership / institution-building
- entrepreneurship
- major creative/research output
- long-term partnership transition (only with appropriate data quality)

### C. Trajectory shape
- early acceleration vs late bloom
- volatility index
- domain-switch count
- geographic mobility
- institution dependence vs independent path
- output concentration vs steady accumulation

## Not user-facing targets
Mortality, medical events, crime, or other high-stakes outcomes may be studied only as aggregate research questions if lawful and ethically justified; they are excluded from consumer predictions.

## Leakage policy
For a cutoff at age 25:
- Allowed: birth data, events dated <=25, education already completed/started by 25, location history <=25.
- Forbidden: later biography text, future awards, final occupation labels derived from later life, retrospective summaries that mention future achievements.

## Evaluation
- macro-F1 for archetypes
- Brier score and expected calibration error for probabilities
- time-dependent concordance / integrated Brier for event timing
- top-k retrieval consistency
- subgroup calibration by era / geography / sex where legally and ethically appropriate
- real vs shuffled-birthday delta with bootstrap CI

## Prediction credit
A retrospective match never counts as a prediction. Public forecast accuracy is calculated only from claims written to the immutable ledger before the event window.
