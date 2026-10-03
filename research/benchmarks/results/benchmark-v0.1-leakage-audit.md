# Benchmark v0.1 leakage & confounding audit

Date: 2026-10-03

## Bottom line

No direct target leakage has been found in Benchmark v0.1.

However, the small apparent BaZi advantage over the original raw-birth baseline is **not evidence of metaphysical signal**. Several weaker-but-important confounders remain, and a fairer calendar baseline shrinks most of that gap.

## Direct leakage checks

### 1. Person separation
All 20 benchmark splits use `GroupShuffleSplit(..., groups=person_id)`.

Audit result: **0 shared people between train and test in all 20 splits**.

Multiple cutoffs from the same person stay in the same partition.

### 2. Temporal feature boundary
For a cutoff age (t):
- past event features require `age_max <= t`
- target event requires `age_min > t`

Therefore the target event itself is not counted in past-event features.

### 3. Birth-only BaZi
Compact BaZi features are deterministic functions of birth date/time only. No biography, occupation, award, event subject, or future event information is passed into the BaZi feature builder.

### 4. Identity linkage
Astro-Databank → Wikipedia → Wikidata links are gated by exact birth-date agreement before entering the primary timed cohort.

The first validated linkage run found:
- 3,093 verified day matches
- 288 day mismatches rejected
- 109 Wikidata records with insufficient birth precision
- 544 Wikidata birth dates missing
- 38 unresolved QIDs

This removed obvious wrong-person joins.

### 5. Shuffled-label negative control
Using the real BaZi model predictions but repeatedly shuffling the test labels produced:

- mean Macro-F1: **0.2453**
- 5th–95th percentile: **0.2288–0.2650**

This is consistent with a no-signal multiclass control. There is no sign that target information is directly embedded in the feature matrix or scoring path.

## Important non-leakage confounders

### A. Outcome-conditioned row inclusion
Benchmark v0.1 only creates a row if at least one future structured event is observed after the cutoff.

That means the sample is conditioned on future documentation. This is a selection/collider bias and must be fixed with censor-aware event/no-event targets.

### B. Retrospective documentation
Wikidata biographies are observed retrospectively. A historical event that occurred before the cutoff is treated as available state information even if it was added to Wikidata decades later.

This is acceptable for an omniscient historical-state benchmark, but it is **not equivalent to a real-time forecast made at that historical date**.

### C. “Next documented event” is not “next real event”
The target is the next event recorded in structured Wikidata, not necessarily the next important thing that actually happened.

Documentation density depends on fame, occupation, era, geography, language coverage, and source culture.

### D. Cohort/geography/season confounding
BaZi is a deterministic transformation of calendar time. Calendar time can correlate with:
- birth cohort
- season
- geography
- institutional calendars
- historical recording practices

The original placebo shuffled BaZi within birth decade only, which was not strict enough.

An exact-birth-year shuffle still left a small difference in a preliminary 5-split audit:
- real BaZi-only Macro-F1: **0.2712**
- exact-year shuffled BaZi: **0.2584**

This removes coarse cohort as the sole explanation, but geography and seasonal confounding remain.

## Fairer raw-calendar control

The original raw-birth baseline fed year/month/day/hour/minute as plain linear numbers. That is an unfair comparison against BaZi, which performs nonlinear cyclical feature engineering.

Adding simple cyclical calendar encodings (month, day-of-year, hour, 60-year phase) raised the raw-calendar Macro-F1 to:

**0.2647 ± 0.0157**

versus compact BaZi:

**0.2692 ± 0.0173**

So the original ~0.010 BaZi-over-raw gap shrinks to roughly **0.0045 Macro-F1** under a more comparable calendar representation.

That residual is too small to interpret without stricter controls.

## BaZi ablation

20 person-level splits:

| Feature group | Macro-F1 |
|---|---:|
| Element / elemental-balance features | **0.2800 ± 0.0088** |
| Hidden-stem counts | 0.2701 ± 0.0103 |
| Ten-God counts | 0.2623 ± 0.0194 |
| Branch/stem relation rules (冲合刑害 etc.) | **0.2494 ± 0.0233** |

The strongest apparent signal currently comes from elemental/calendar-derived encodings, not the traditional relational rule layer.

This pattern is more compatible with calendar/season feature engineering or confounding than with a claim that traditional fate rules have been validated.

## Current interpretation

1. Direct leakage: **not found**.
2. Useful incremental BaZi signal beyond reality history: **not found**.
3. Small BaZi-over-calendar residual: **still unresolved**.
4. Most plausible next explanations to eliminate:
   - nonlinear calendar encoding advantage
   - seasonal/geographic confounding
   - retrospective documentation bias
   - public-figure selection bias
   - outcome-conditioned sampling

## Required v0.2 tests

- censor-aware event/no-event modeling
- forward-era holdout
- geography holdout
- exact-year + geography-stratified placebo
- raw calendar baseline with equal model capacity
- 3-pillar vs 4-pillar on the same people
- feature-group ablation reported by default
- biography-text enrichment with source/revision provenance
