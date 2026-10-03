# Cohort policy v1

MingGui must never collapse all people into one undifferentiated training population.

## Cohort A — broad historical day-level cohort

**Sources:** Wikidata + BHHT / Pantheon enrichment.

Purpose:
- three-pillar / date-level experiments
- career, migration, creation, organization and recognition trajectories
- large-scale reality baseline

Limitations:
- overwhelmingly people notable enough to have biographies
- biography completeness correlates with fame, geography, era and language
- no trustworthy birth hour from Wikidata

Outputs from this cohort must be described as conditional on a **public-biography/notable-person cohort**, not general-population life probability.

## Cohort B — high-quality timed-birth cohort

**Primary source:** Astro-Databank under applicable license.

Primary research strata:
- AA: strongest timed-birth evidence
- A: strong quoted/personal source
- B: biographical/historical source

Sensitivity-only:
- C / DD: uncertain/conflicting; never mix silently into the primary timed cohort
- X-family: no usable birth time, may join date-only experiments but not four-pillar experiments

Purpose:
- test whether adding the hour pillar improves prediction
- test timing-sensitive traditional rules
- compare three-pillar vs four-pillar models **on the same people**

Raw licensed exports stay private and out of git. Public artifacts may contain aggregate metrics only where license permits.

## Cohort C — Chinese historical research cohort

**Source:** CBDB, strictly version/license bounded.

Purpose:
- historical Chinese education/exam/office/network trajectories
- investigate whether locally-developed metaphysical features behave differently in Chinese historical populations

This cohort remains separated from any commercial/public-service use unless licensing clearly permits it.

## Cohort D — prospective ordinary-user cohort

Opt-in MingGui users whose predictions are locked before outcomes occur.

Purpose:
- reduce famous-person selection bias
- become the strongest genuine future-validation set
- calibrate probabilities for ordinary modern users

Requirements:
- explicit research consent separate from product consent
- de-identification for modeling
- deletion/export rights
- no high-stakes target predictions
- never retroactively rewrite forecast records

## Cross-cohort reporting

Every metric must state:
- cohort id/version
- birth-data precision stratum
- era range
- geography distribution
- notability distribution
- target maturity/right-censoring rule
- source completeness thresholds

A model trained on Cohort A can generate *hypotheses* for a normal user, but its raw frequency is not a population base rate.
