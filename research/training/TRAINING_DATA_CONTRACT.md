# Training data contract

MingGui training data is materialized, audited, fingerprinted, and frozen before model fitting. Training code must consume the frozen training dataset and feature snapshots; it must not reconstruct labels from mutable raw tables.

## Final training dataset

Primary frozen dataset:

- dataset key: `next-observed-canonical-event-domain`
- version: `v1.0-final`
- training dataset id: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- source snapshot: `v1.0-final-identity`
- source snapshot id: `42628250-3a51-4b92-b4bd-12c7dec846a8`
- observation cutoff: 2026-10-05
- people: 3,398
- cutoff ages: 18 / 25 / 30 / 40
- rows: 13,592
- observed classification targets: 7,465
- censor-aware eligible rows: 13,129
- right-censored rows: 5,664
- cutoff-after-observation-window rows: 463
- rows with non-empty observed history: 3,879
- status: `frozen`
- readiness: `training_ready=true`

No person or cutoff row is removed merely because the biography is sparse or no future event is documented.

## Frozen source snapshot

The source snapshot contains:

- 3,398 people
- 31,710 raw event memberships
- 31,512 snapshot-model-eligible raw events
- 31,655 conservative canonical event facts
- exact person membership SHA-256: `ddf9631abaa04cfa89ce0810d3ba1b4fa2ca6bb6cfa033bbfc81c6a74f8e05da`
- exact raw-event membership SHA-256: `be680992ce8b188f107cfac31f9c384311071701c032ca73722fe51de9712003`
- canonical-event SHA-256: `88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654`

Identity gate:

- verified day-level identity match
- one-to-one unique Wikidata QID
- 3,398 verified identities
- 0 API-loss QIDs

The snapshot is immutable. New biography sources, corrections, or geography coverage must create a later snapshot/version rather than mutate v1.0.

## Raw data preservation

Raw source-backed events are never deleted merely because they are unsuitable for a model.

Three concepts are kept separate:

1. **Raw existence** — the source record/event is preserved.
2. **Intrinsic model eligibility** — whether that raw event has sufficient valid timing/semantics for trajectory modeling.
3. **Snapshot eligibility** — whether the event was observable by the frozen snapshot cutoff.

Invalid or unusual records remain queryable with quality flags and exclusion reasons.

## Canonical events

Training labels use `exact-subject-v1` canonicalization.

This rule is intentionally conservative. Raw events merge only when they agree on:

- person
- domain
- event type
- date interval
- qualifier
- non-empty subject external ID

Subjectless events remain distinct. No fuzzy semantic or language-model deduplication is used in v1.0.

For the frozen final source snapshot:

- raw memberships: 31,710
- canonical facts: 31,655
- exact duplicate memberships collapsed: 55

Every canonical fact retains all underlying raw event keys and source provenance.

## Target semantics

The task predicts the **next documented canonical model-eligible event domain**, not the next true event in a person's life.

For each person and cutoff age:

1. Determine the cutoff date from the frozen birth record.
2. Determine the observation end.
3. Build history from canonical events observable by the cutoff.
4. Choose the earliest eligible future canonical event ordered by:
   - `observable_from`
   - event date
   - canonical event key

The raw representative target event key and all raw target provenance keys are retained.

Primary 4-class benchmark mapping:

- career
- recognition
- relationship
- other

Raw domains are never overwritten. Raw-domain metrics are also reported as diagnostics.

Observed target counts in v1.0:

- other: 3,103
- career: 1,979
- recognition: 1,489
- relationship: 894

The raw-domain distribution includes, among others, creation (1,681), family (672), education (348), and organization (273).

## Feature snapshots

Every person-cutoff row has one immutable `research.feature_snapshots` row.

Feature spec:

`bazi-objective-v0.1+canonical-history-v1`

Allowed top-level feature payload:

- `spec_version`
- `cutoff_age`
- `background`
- `raw_birth_calendar`
- `four_pillars`
- `objective_bazi_features`
- `bazi_quality_flags`
- `history`

The feature snapshot stores both:

- exact raw history event keys used as provenance
- exact canonical history event keys used for modeled history

The payload explicitly excludes:

- future events
- target event
- final biography/event coverage totals
- total future domain/source counts
- future observation profile
- final occupations/awards or any post-cutoff personal outcome

## Observation window and censoring

Observation end is:

1. exact death date, if known, bounded by the snapshot cutoff;
2. otherwise December 31 of the known death year, bounded by the snapshot cutoff;
3. otherwise the snapshot cutoff date.

If cutoff is within the observation window but no eligible future target is documented, the row is retained with `right_censored=true`.

If cutoff is after the observation window, the row is retained for completeness but excluded from trajectory fitting.

Censored rows are **never** encoded as a negative/no-event classification class.

## Split scenarios

All splits are by person identity. A person never crosses splits inside a scenario.

### person_hash_v1

The 3,076 people already present in `v0.2-pretrain` retain their exact old split, fold, and assignment hash.

Only the 322 new final-cohort people receive new deterministic assignments.

Final people counts:

- train: 2,350
- validation: 507
- test: 541

### forward_era_v1

- birth year <= 1925: train
- 1926-1950: validation
- 1951+: test

### geo_us_holdout_v1

- US: test
- France: validation
- all other / unknown birth geography groups: train

### geo_france_holdout_v1

- France: test
- US: validation
- all other / unknown birth geography groups: train

Geography holdouts use frozen birth geography fields. Present-day Wikidata geography enrichment is stored separately and is not silently treated as historical nationality.

## Feature variants

Frozen benchmark variants:

- `history_reality_v1`
- `raw_birth_calendar_v1`
- `bazi_objective_only_v1`
- `history_plus_bazi_v1`
- `bazi_decade_shuffle_placebo_v1`

The scientific question is incremental predictive value, not deterministic fate:

- Does BaZi outperform raw calendar controls?
- Does BaZi add lift beyond observed life history?
- Does true BaZi outperform a matched shuffled-BaZi placebo?

## Placebo mapping

The placebo is frozen before model fitting.

Mapping rules:

- unit: person
- same split scenario
- same split
- same birth decade
- deterministic hash order
- circular donor shift
- donor must not be self

Groups with only one person cannot satisfy a derangement. Those people are excluded **only from the placebo variant** and remain in all real-feature experiments.

Frozen placebo mapping SHA-256:

`3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e`

No mapping-integrity violations were found.

## Benchmark protocol

Protocol key:

`next-canonical-domain-benchmark-v1`

Primary metrics:

- macro-F1
- balanced accuracy
- multiclass log loss

Calibration metrics:

- multiclass Brier score
- expected calibration error (ECE)

Secondary diagnostics:

- accuracy
- per-class precision / recall / F1
- raw-domain macro-F1 and per-class support
- paired bootstrap confidence intervals on held-out predictions

Class weights, if used, must be derived **only from the training partition of each split scenario**. Validation/test label frequencies must not influence training weights.

Frozen `sample_weight` is intentionally null. Fit-only weights belong to a model run, not to the dataset.

Hyperparameters are selected on validation only. The test partition is evaluated only after the run configuration is frozen.

## Leakage and integrity audits

The v1.0 dataset has 21 error-level audits (20 core + placebo integrity), all passing, plus non-blocking warnings.

Error-level checks include:

- exact person and row counts
- exact feature snapshot count
- target strictly after cutoff
- target within observation window
- censored rows have no target
- raw history provenance observable by cutoff
- canonical history snapshot-eligible and observable by cutoff
- history key cardinalities match stored history counts
- target absent from raw and canonical feature history
- feature payload allowlist
- no explicit future feature keys
- objective BaZi payload coverage
- observation-end rule reproduction
- target canonical membership/provenance integrity
- snapshot-eligible event ages non-negative
- no snapshot-eligible event after 2026-10-05
- person split isolation in every scenario
- exact preservation of all legacy v0.2 person splits
- final identity snapshot has zero API loss
- all dataset fingerprints are present
- placebo donor mapping integrity

Warnings:

- conservative canonicalization collapsed 55 exact duplicate memberships
- geography enrichment is missing for 305 people; missingness is retained and not imputed

## Fingerprints

Frozen component SHA-256 values:

- samples / labels: `5a5d4295bb27647c7e1b3611b1cb54859e82f06c6bcf315fac8d8f1a38f8320c`
- feature snapshots: `ec3ebdc3cc823b55ea9777de78e4e4ba028ddb5ae5aac8eddbd283296e20688a`
- split assignments: `e02afe8717dadbfad8546fb905a9c4d52e0b4988ea6ef1bad9f8bf274bf9d5d1`
- source canonical events: `88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654`
- combined training dataset: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- placebo mapping: `3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e`

Never overwrite v1.0. Any change to identities, raw facts, canonicalization, label semantics, feature construction, split rules, or placebo mapping requires a new version.
