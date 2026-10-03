# Data status — 2026-10-03

Real source files have now been acquired and inspected.

## Acquired

### BHHT cross-verified notable people
- 2,291,817 rows
- every row has a Wikidata QID
- 2,095,898 have a birth-year value
- 11,790 are Pantheon-linked
- official Sciences Po file acquired successfully

**Important:** BHHT is an excellent biography/notability backbone, but its public table is primarily year-level for birth. It cannot directly generate month/day-sensitive BaZi features. Exact P569 is enriched from Wikidata for selected training cohorts.

### Pantheon 1.0
- 11,341 biographies
- MD5 exactly matches Harvard Dataverse
- 10,294 have coordinates
- rich manually verified occupation/domain/notability metadata

Pantheon is used as a quality benchmark and overlap stratum, not as a birth-hour source.

### Astro-Databank free C sample
- 6,036 records in the currently downloaded sample
- AA: 3,825
- A: 1,161
- B: 233
- primary timed-birth cohort (AA/A/B): **5,219**
- 4,580 records contain a Wikipedia link
- 5,940 Gregorian, 96 Julian-calendar birth records

This is the first real four-pillar cohort. Only fields from `public_data` are normalized for our birth table. `research_data`, source notes, and copyrighted biography text are not redistributed.

## Running now

1. Build Pantheon-linked BHHT cohort.
2. Enrich it with precision-aware Wikidata P569 statements.
3. Resolve timed-birth AA/A/B records to Wikidata where possible.
4. Fetch dated public Wikidata life claims for the timed cohort.
5. Generate normalized artifacts and coverage reports.

## Next scale-up

After the 11.8k overlap cohort is validated, build a larger **stratified BHHT exact-date cohort** across:
- region
- occupation family
- birth era
- notability/completeness tier

This is preferable to simply taking the globally most famous people because that would amplify Europe/US and occupation-selection bias.

For the full 2.29M biography universe, keep BHHT as the year-level reality baseline and use Wikidata dumps for eventual exact-date enrichment at scale. Wikidata itself recommends dumps when the desired result set is very large.


## Balanced exact-date cohort result

The first balanced 100,000-person BHHT cohort has now completed.

Sampling frame:
- 1,905,682 eligible BHHT records (1800–2005, non-missing score >= 2)
- 908 non-empty strata
- dimensions: region × level-1 occupation × birth era × Wikipedia-edition tier
- deterministic within-stratum sampling with inverse sampling weights

Wikidata P569 enrichment:
- requested: 100,000
- people with any birth assertion: 98,979
- people with day precision: 84,255
- day precision + BHHT birth-year agreement: 83,017
- people with multiple/conflicting source values are retained rather than silently overwritten

Conflict-safe provisional canonicalization of the completed artifact:
- canonical unique day: 78,491
- canonical preferred day: 3,564
- **primary unambiguous day-level total: 82,055**
- conflicting day values: 962
- year-only: 13,874
- month-only: 695
- no eligible day-level value: 1,393

For the calendar-conservative first BaZi experiment, 63,055 canonical records are born in 1900 or later. Pre-1900 records remain available but are held out of the primary experiment until the source calendar model is reliably preserved/normalized.

The 100k sampled cohort itself is materially less Europe-heavy than the full BHHT population:
- Europe 35,752
- America 26,078
- Asia 15,543
- Oceania 9,190
- Africa 8,418
- missing region 5,019

This is now large enough for the first serious three-pillar benchmark.
