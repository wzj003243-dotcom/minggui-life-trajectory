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
