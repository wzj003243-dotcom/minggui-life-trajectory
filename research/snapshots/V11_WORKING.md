# v1.1 working source snapshot

MingGui v1.0 remains immutable. All post-v1.0 enrichment is isolated in a copy-on-write v1.1 branch.

## Working snapshot

- snapshot ID: `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`
- dataset key: `timed-core`
- version: `v1.1-working`
- status: `draft`
- parent: `42628250-3a51-4b92-b4bd-12c7dec846a8 / v1.0-final-identity`

Baseline membership was copied exactly from frozen v1.0:

- people: 3,398
- raw event memberships: 31,710
- snapshot-model-eligible raw events: 31,512

Parent frozen fingerprints retained only as lineage metadata:

- person membership: `ddf9631abaa04cfa89ce0810d3ba1b4fa2ca6bb6cfa033bbfc81c6a74f8e05da`
- raw event membership: `be680992ce8b188f107cfac31f9c384311071701c032ca73722fe51de9712003`
- canonical events: `88f5bf90c86424a626e4c1bd7b14709c41170a0cc6fc48f9d400754b25ad4654`

These are parent hashes, not v1.1 freeze hashes. v1.1 must recompute membership and canonical fingerprints before it can become frozen.

## Copy-on-write rules

- Never modify frozen v1.0 membership to add an enrichment.
- New source records, candidates, events, corrections, and memberships belong to `v1.1-working`.
- Preserve raw/candidate data even when a record is not model-eligible.
- Model eligibility and snapshot eligibility remain separate from raw existence.
- Canonicalization is recomputed only after enrichment import/audit.
- v1.1 must receive a new observation cutoff, hashes, counts, training dataset ID, splits/placebo map, and benchmark protocol before model fitting.

## First enrichment priority

The first v1.1 enrichment is full-cohort revision-pinned Wikipedia biography coverage.

The old v1.0 biography artifact covered only a selected 300-person subset. The previous all-cohort sequential workflow could time out before completion. The v1.1 workflow therefore uses four deterministic QID shards with at most two concurrent jobs:

`.github/workflows/v11-biography-sharded.yml`

Each shard preserves raw revision-pinned wikitext, date-bearing timeline candidates, precision-first rule events, extraction reports, and source provenance.

No shard is imported into v1.0.


## Baseline snapshot facts

The v1.1 working snapshot also contains an exact baseline copy of all **3,398** frozen `person_snapshot_facts` rows from v1.0, including birth/death facts and frozen geography fields. These copies are tagged with:

- `inherited_from_snapshot = 42628250-3a51-4b92-b4bd-12c7dec846a8`
- `inheritance_mode = baseline-copy`

This keeps v1.1 self-contained for enrichment age checks and later audits. New corrections, if any, must be explicit v1.1 changes rather than edits to v1.0.

## Authorized shard imports

v1.1 external artifacts are imported through the private `research.artifact_import_authorizations` allowlist.

An import is accepted only when all of the following match an approved row:

- importer key,
- provider,
- provider artifact ID,
- exact SHA-256,
- target snapshot.

The biography importer is `minggui-v11-biography-import` and targets only:

`7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`

The Edge Function remains JWT-required except for the short, explicit GitHub Actions import window. Exact ZIPs are archived in private Storage.

## Freeze gate

Do not canonicalize or freeze v1.1 until all planned biography shards have been:

1. downloaded successfully;
2. SHA-pinned;
3. archived;
4. imported with raw candidates preserved;
5. audited for shard overlap, identity misses, invalid/pre-birth events, and source revision completeness.

Only then recompute canonical events, membership hashes, counts, eligibility, and a new training dataset.


## Wikipedia revision supersession policy

Wikipedia biography enrichment is revision-pinned. A person may therefore have an older v1.0 revision and a newer v1.1 revision.

v1.1 preserves **all** old raw events, candidates, evidence, and memberships, but the model-facing snapshot must not count multiple Wikipedia revisions of the same biography simultaneously.

For every person with a successfully fetched v1.1 biography revision:

- previous `rule-from-revision-text` Wikipedia events remain stored;
- their v1.1 `dataset_event_membership.snapshot_model_eligible` is set to `false`;
- `exclusion_reason = superseded_by_v11_biography_revision`;
- metadata records the superseding v1.1 artifact and revision;
- rule events extracted from the current revision become the active v1.1 Wikipedia narrative layer.

This is a snapshot-local eligibility change. It never mutates or deletes the frozen v1.0 snapshot and never deletes historical evidence.
