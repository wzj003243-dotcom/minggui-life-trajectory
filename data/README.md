# Data model

MingGui separates **what happened**, **what a source claims**, and **what the model derives**. Never collapse these into one biography row.

## Canonical layers

### 1. `people`
Stable identity only: internal person id, source identifiers, canonical display name, aliases and broad public metadata.

### 2. `birth_assertions`
One row per source claim about a birth date/time/place. Multiple contradictory rows are allowed.

Important fields:
- date/time value
- date precision (year / month / day / minute)
- time-zone confidence
- place id / coordinates
- source id and source reliability
- whether the claim is selected as canonical for a particular experiment

The training pipeline must never silently replace uncertain birth times with noon or midnight.

### 3. `life_events`
Atomic, source-backed timeline events. Events use age/date **intervals** when the exact date is unknown.

Examples:
- education.start
- migration.cross_country
- career.domain_change
- work.publication
- recognition.award
- organization.founded

### 4. `source_records`
Provenance for every assertion/event: URL or dataset key, retrieval date, license bucket, extraction method, confidence, and source snapshot/version.

### 5. `feature_snapshots`
Derived features for a specific person **at an information cutoff**. This is the unit used by prediction models.

### 6. `targets`
Future outcomes calculated only from events after the cutoff. Target builders are versioned and reproducible.

## Precision rules

Dates are never forced to fake precision:
- `9` = year
- `10` = month
- `11` = day
- `12+` = sub-day precision

For generic sources use our normalized enum: `year | month | day | hour | minute | exact | disputed`.

## Cross-source policy

A fact can be:
- **single-source**
- **cross-verified**: independent sources agree
- **conflicting**
- **unresolved**

Training cohorts may choose stricter thresholds. The default historical benchmark should prefer records with at least two independent sources when possible.

## Git policy

Raw third-party dumps, processed Parquet datasets, model weights, and private user timelines are gitignored. The repository contains schemas, manifests, extraction code, tiny synthetic fixtures, and reproducible recipes.
