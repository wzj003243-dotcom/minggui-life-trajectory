# Training data contract

MingGui training data is materialized and versioned before model fitting. Training code should not reconstruct labels or historical features directly from raw tables.

## Current preflight dataset

`next-observed-event-domain / v0.2-pretrain`

This dataset is deliberately **not final**. It is marked `preflight-passed-awaiting-final-identity` because two historical Wikidata validation runs suffered different 400-QID API batch failures. A lossless identity rebuild is in progress.

Current mother table:

- people: 3,076
- cutoff ages: 18 / 25 / 30 / 40
- rows: 12,304
- classification-eligible rows: 5,708
- censor-aware eligible rows: 11,887
- right-censored rows: 6,179
- cutoff-not-observed rows: 417

No censored person-cutoff row is deleted merely for lacking a future documented event.

## Target semantics

The first task predicts the **next documented model-eligible event domain**, not the next true life event.

Raw domains are retained. The first benchmark uses:

- career
- recognition
- relationship
- other

Rare raw classes such as migration and creation stay in the database and are only mapped to `other` for that benchmark.

## Feature snapshots

Every person-cutoff row has one immutable `research.feature_snapshots` record.

Allowed feature payload:

- birth-fixed BaZi objective features
- four pillars
- BaZi quality flags
- historical event summary observable by cutoff
- historical event/domain/source/stage counts
- cutoff age

The snapshot also stores the exact historical `event_key[]` used.

It explicitly does **not** contain total future biography coverage, final occupation, future awards, or any later event.

## Censoring

`observation_end_date` is bounded by the frozen dataset snapshot date and by exact death date when available.

If no future documented target exists but the cutoff is inside the observation window, the row is kept with `right_censored=true`.

If the cutoff occurs after the observation window, the row is retained but is not eligible for trajectory training.

## Split scenarios

All splits are by person identity. A person never appears in two splits inside the same scenario.

- `person_hash_v1`: deterministic 70/15/15 baseline.
- `forward_era_v1`: birth year <=1925 train, 1926–1950 validation, 1951+ test.
- `geo_us_holdout_v1`: United States test, France validation, all other normalized geography groups train.
- `geo_france_holdout_v1`: France test, United States validation, all other groups train.

Raw birthplace/country strings are retained. Geography holdouts use `birth_country_normalized` / `birth_geo_group`.

## Leakage audits

A dataset is not trainable-final until every error-level audit passes.

Audits include:

- exact person-cutoff row count
- person split isolation
- target strictly after cutoff
- target within observation window
- censored rows have no target
- target event is model-eligible
- one feature snapshot per person-cutoff
- all feature event keys are observable by cutoff
- feature event-key count matches historical event count
- target event is absent from feature event keys
- feature payload top-level allowlist
- model-eligible event ages are non-negative
- final identity snapshot has zero external API loss

The current preflight dataset passes every leakage/integrity audit except the final identity-snapshot requirement.

## Fingerprints

The dataset stores independent SHA-256 hashes for:

- sample rows / labels
- feature snapshots
- split assignments

and a combined `fingerprint_sha256`.

Never overwrite a frozen final dataset. Rebuild under a new version if any input, label, feature, split, or identity record changes.
