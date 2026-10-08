# MingGui v1.1 — Frozen Source Snapshot Readiness

This document records the finished source data snapshot, **not** a trained v1.1 model.

## Identity and immutability

- Snapshot ID: `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`
- Database version string: `v1.1-working` (historical creation label; **status is frozen**)
- Source snapshot status: **frozen**
- Observation cutoff: **2026-10-06**
- Actual freeze timestamp: **2026-10-08 01:40:40 UTC**
- Freeze spec: `snapshot-freeze-v4`
- Canonicalization: `exact-subject-v1`
- Frozen parent v1.0: `42628250-3a51-4b92-b4bd-12c7dec846a8`
- Lineage: copy-on-write. The v1.0 memberships and fingerprints were verified unchanged.

## Frozen data counts

| Metric | Frozen v1.0 | Frozen v1.1 |
|---|---:|---:|
| People | 3,398 | 3,398 |
| Raw event memberships | 31,710 | **37,425** |
| Model-eligible raw memberships | 31,512 | **36,982** |
| Canonical event facts | 31,655 | **37,370** |
| Model-eligible canonical event facts | — | **36,927** |

The 37,425 raw membership rows are represented by 37,370 canonical facts; only strict exact-subject duplicates collapse at the canonical layer, not raw evidence. Canonical fact provenance references still sum to **37,425** raw event memberships.

## Wikipedia full-cohort enrichment

Four finalized source artifacts all came from one successful source workflow run:

- Source run: `37712781470`
- Union audit run: `37713063965`, **success**
- Database import run: `37713758683`, **success**
- Audited import manifest SHA-256:
  `d52eaeb1f6eb57f1861480757d2df8d1e26c02b794c1a4c8a413229afc464673`

| Shard | GitHub artifact ID | Exact ZIP SHA-256 | Biographies | Candidates | Rule events |
|---|---|---|---:|---:|---:|
| 0 | `11522073073` | `28ef47b658ef6f37bbf0c26f40f9ca27bedf9cd60277259bef64e7f53d42402b` | 438 | 4,757 | 1,717 |
| 1 | `11522560880` | `69bbf194c366eeaba7b2d3153481b0d7862d739d7fc8bbbc311139680dbaaeb5` | 435 | 4,461 | 1,550 |
| 2 | `11522815760` | `020a1b5e013c65cfa2837dec1a6113039ea4431e67c887f3011dc39be062b8ce` | 577 | 5,439 | 2,033 |
| 3 | `11522064966` | `1e2c43b9809549543c60f03be883cabad7bfe67fedd1a27d21d31f1fc995168e` | 569 | 6,025 | 2,018 |
| Total | | | **2,019** | **20,682** | **7,318** |

All four source ZIPs are archived in private `research-artifacts` Storage under `v11/biography/`, registered as imported, and pinned by official GitHub SHA-256. Raw Wikipedia revision wikitext remains inside the archived ZIPs; candidate text and rule events remain in the database.

The union audit passed with **zero errors**: exactly 3,398 distinct cohort QIDs, no duplicate biographies/candidate IDs/event IDs, no missing rule-to-candidate references, and no invalid event date intervals.

Explicit warnings: 1,379 cohort people have no matching enwiki/zhwiki revision-pinned biography, and one future event must remain snapshot-ineligible. Missing coverage is preserved, never synthesized.

## Coverage lift

Measured using **snapshot-model-eligible** event memberships per person, over the same frozen 3,398-person cohort:

| Metric | v1.0 | v1.1 |
|---|---:|---:|
| People with zero active events | 1,297 | **950** |
| Mean eligible events/person | 9.274 | **10.883** |
| Median eligible events/person | 2 | **3** |

- **347** previously zero-event people gained at least one active event.
- **1,307** people gained active events overall.
- **0** people experienced a net decrease in active events.

This improvement concerns source-observed life events, not independently verified real-world coverage.

## Post-import safety and quality

- All four authorized source artifacts: imported.
- All **94** authorized chunks: imported.
- Database metadata chunk SHA maps matched the audited ZIP manifest exactly.
- All four artifact registry metadata payloads are JSONB objects, not string-encoded JSON.
- Import Edge Function is **ACTIVE with `verify_jwt=true`** after the import window.
- Supabase security advisor: **0 lints**.
- Future eligible events: **0**.
- Active prebirth events: **0**.
- Active events from Wikipedia revisions after snapshot cutoff: **0**.
- People with multiple active Wikipedia narrative revisions: **0**.
- Older Wikipedia revision memberships explicitly superseded in v1.1: **190**, preserved raw.
- Source revision after snapshot cutoff: **1** rule event excluded from v1.1 model layer.
- Post-cutoff event observations: **42** memberships retained but ineligible.

## Frozen fingerprints

```text
person_membership_sha256
231a9b30cbb7d3ecbad3087aef7f700985e4cff19acdfbdc2c65495afc81dd8d

event_membership_sha256
b52481551e972a82a261de506b17e33d15bd75898ae32e35e0480c348151eb95

canonical_event_sha256
2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf
```

## Next research stage

**No v1.1 model has been trained or tested as part of this freeze.**

Training must materialize a **new v1.1 training dataset** from this frozen source snapshot, never modify the v1.0 training dataset. Recreate historical cutoffs and censor-aware observation windows from v1.1 canonical model-eligible facts; replay all leakage audits, person-level split isolation, and matched placebo BaZi maps. Keep the historical v1.0 test protocol and model comparisons as a locked benchmark.

Compare against v1.0 on the same people and held-out cohorts. Primary question: whether richer source history improves calibrated future event distributions and reduces sparse-history failure modes. The prior v1.0 result did **not** establish incremental predictive value of BaZi, and v1.1 must not assume one.

Any future source corrections or additional scraping belong in v1.2/new snapshot; do **not** mutate frozen v1.1.
