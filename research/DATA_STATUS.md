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
