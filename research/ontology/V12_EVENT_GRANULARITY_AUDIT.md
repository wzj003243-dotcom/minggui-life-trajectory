# v1.2 event-granularity overlay — frozen-source profiling

**Audit date:** 2026-10-08
**Source:** v1.1 frozen canonical snapshot \`7fce3b79-ebfc-40b2-a5f0-e91b28db6a02\`, model-eligible canonical event rows only.
**Overlay:** \`research/ontology/event_granularity_v1.py\`. No source events were deleted, merged, relabeled, or overwritten.

## Why this is essential for lifetime forecasting

The old four-domain R6 baseline collapses many \`creation\`, \`performance\`,
\`education\`, \`migration\`, \`family\` and \`organization\` domains into
\`other\`. This makes it too easy for prolific output records
(e.g. album release or scholarly publication listings) to drown out
fewer, more meaningful life-state changes.

Our objective is NOT to delete any "small" event. Every person's details remain
valuable. Instead, independently represent **life-state transitions**,
**recognition achievements** and **repeatable creative/public outputs**.

## Frozen corpus profiling

| Overlay class | Canonical facts | People represented | Unique event types |
| --- | ---: | ---: | ---: |
| Repeated output | **16,786** | 999 | 6 |
| Life transition | **14,690** | 2,006 | 25 |
| Achievement | **4,256** | 1,121 | 1 |
| Unclassified / audit needed | **1,195** | 533 | 34 |
| **All** | **36,927** | not additive | 66 |

In particular:
- \`creation.music_release_group\`: **10,438** facts from **451** people.
- \`creation.scholar_work\`: **1,622** facts from only **11** people.
- \`career.position.start/end\`, \`relationship.marriage\`,
  \`family.child_birth\`, \`migration.cross_region\`,
  \`education.complete\` and similar transitions are distinct from output counts.

The figures above are **dataset composition**, not population incidence or
event importance estimates. Some "transitions" can recur and some outputs may
constitute major turning points; this conservative overlay is a modeling
separation, not a universal judgment of significance.

## New modeling contract

1. Preserve every original event and its source lineage, exact event type,
   subject, precision and time evidence.
2. Add a **derived** \`model_granularity_v1\` field. Unknown types remain
   \`unclassified\`, retained for manual review rather than silently mapped to \`other\`.
3. Train separate, calibrated observation processes for transitions, achievements,
   and repeatable output; permit them to coexist in the same year.
4. Measure both the **occurrence** and **repeat count** in each category.
   Heavy-tailed prolific-creator counts require an explicit count model / dispersion check.
5. Do not interpret a higher count of documented releases, awards or positions
   as proof of a more eventful or more significant actual life.
6. Separate autobiographical transition probability from the opportunity for
   biographical coverage, celebrity concentration, historical era and occupation.
7. Future event prediction must use truly cutoff-available evidence;
   source revision timestamps are necessary for credible retrospective replay.

## Decision

Round 6's 18–87 age/history fitted rates prove that the infrastructure can
learn *documentation dynamics*, **not** that we can now predict a normal
person's life stages. The next empirical comparison should use these granularity
heads and fresh holdouts before authoring personalized life narrative outputs.
