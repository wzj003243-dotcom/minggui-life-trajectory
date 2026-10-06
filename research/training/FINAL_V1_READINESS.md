# Final v1 training readiness

Status: **READY FOR MODEL TRAINING**

Frozen dataset:

- training dataset: `next-observed-canonical-event-domain / v1.0-final`
- training dataset id: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- source snapshot: `timed-core / v1.0-final-identity`
- source snapshot id: `42628250-3a51-4b92-b4bd-12c7dec846a8`
- observation cutoff: 2026-10-05
- people: 3,398
- rows: 13,592
- observed targets: 7,465
- right-censored rows: 5,664
- cutoff-after-observation rows: 463

Source graph:

- raw event memberships: 31,710
- snapshot-model-eligible raw events: 31,512
- conservative canonical facts: 31,655
- exact duplicate memberships collapsed: 55

Feature snapshots:

- rows: 13,592
- spec: `bazi-objective-v0.1+canonical-history-v1`
- leakage audit passed: all rows
- rows with non-empty observed history: 3,879

Split integrity:

- all scenarios split by person, never by cutoff row
- legacy v0.2 people preserved exactly: 3,076
- legacy split changes: 0
- newly assigned final-cohort people: 322
- person-hash people: train 2,350 / validation 507 / test 541

Primary observed-target 4-class distribution:

- other: 3,103
- career: 1,979
- recognition: 1,489
- relationship: 894

Target-source distribution:

- Wikidata: 6,109
- MusicBrainz: 1,084
- Wikipedia: 236
- OpenAlex: 36

Negative control:

- frozen placebo donor mapping: `bazi_decade_shuffle_placebo_v1`
- same scenario split + same birth decade
- deterministic circular derangement
- self-donor violations: 0
- mapping SHA-256: `3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e`
- singleton groups are placebo-ineligible only; real-feature rows are retained

Audits:

- error-level audits: 21
- failed error-level audits: 0
- non-blocking warnings: conservative exact canonicalization; incomplete optional geography coverage
- Supabase security advisor: 0 findings
- missing-PK / uncovered-FK performance findings introduced by final-v1 schema: resolved

Raw artifact durability:

The frozen final identity core, multisource source bundle, MusicBrainz enrichment, Wikipedia biography enrichment, family/degree, founding, notable-work, and geography artifacts are copied into private Supabase Storage and registered with exact SHA-256 provenance. One-off importer Edge Functions require JWT after the freeze.

Fingerprints:

- person membership: `ddf9631abaa04cfa89ce0810d3ba1b4fa2ca6bb6cfa033bbfc81c6a74f8e05da`
- raw event membership: `be680992ce8b188f107cfac31f9c384311071701c032ca73722fe51de9712003`
- canonical source events: `88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654`
- training samples / labels: `5a5d4295bb27647c7e1b3611b1cb54859e82f06c6bcf315fac8d8f1a38f8320c`
- feature snapshots: `ec3ebdc3cc823b55ea9777de78e4e4ba028ddb5ae5aac8eddbd283296e20688a`
- split assignments: `e02afe8717dadbfad8546fb905a9c4d52e0b4988ea6ef1bad9f8bf274bf9d5d1`
- combined training dataset: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`

Frozen benchmark protocol:

`next-canonical-domain-benchmark-v1`

Compare:

1. history reality
2. raw birth calendar
3. objective BaZi only
4. history + objective BaZi
5. matched shuffled-BaZi placebo

Across:

1. person-hash split
2. forward-era holdout
3. US geography holdout
4. France geography holdout

Primary metrics:

- macro-F1
- balanced accuracy
- multiclass log loss

Calibration:

- multiclass Brier score
- expected calibration error

Raw-domain macro-F1 and per-class support must be reported as diagnostics so the pooled `other` class cannot hide source/domain behavior.

Training weights, if used, are computed only from the training partition of each scenario. Validation/test frequencies must never influence fitting.

No model has been fit as part of this readiness freeze.
