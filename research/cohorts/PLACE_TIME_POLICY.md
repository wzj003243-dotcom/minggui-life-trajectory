# Place & birth-time policy

Birth place and birth time are separate evidence problems.

## Wikidata
Wikidata is valuable for:
- birth **date** to documented precision
- birthplace entity id
- place coordinates and geographic hierarchy

It is not a reliable source of precise birth hour. The timestamp representation and its trailing `Z` must not be treated as a UTC birth instant.

## Dedicated timed-birth sources
A four-pillar experiment requires an explicit timed-birth assertion with provenance/reliability. The source must identify whether the recorded time is:
- local civil time
- converted time
- approximate / rounded
- rectified by an astrologer

## Historical timezone
Do not apply today's UTC offset backward to a historical birth automatically. Political timezone rules and daylight-saving history change.

The canonical data model therefore stores:
- reported local birth time
- source-reported timezone/offset when available
- normalized IANA zone when defensible
- conversion method/version
- confidence

## True solar time
Different BaZi traditions disagree about whether/how to use true solar time. MingGui must treat this as an **experimental transformation**, not silently choose one school.

For timed cohorts we should be able to generate parallel feature variants:
1. source-reported local civil time
2. historically normalized civil time
3. longitude/solar-time adjusted variant

Then compare their held-out predictive performance on the same cohort.
