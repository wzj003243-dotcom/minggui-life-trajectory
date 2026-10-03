# Biography → life-event extraction contract v1

The goal is **not** to summarize a biography. The goal is to create a leakage-safe event sequence.

## Extract only observable events

Good:
- “entered University X in 1998” → `education.start`
- “moved to Paris in 2004” → `migration.city/cross_country`
- “published first novel in 2011” → `creation.publication`
- “founded Company Y in 2016” → `organization.found`

Bad:
- “was destined for greatness”
- “became one of the most influential…”
- “his early struggles foreshadowed…”
- any retrospective interpretation that encodes later outcomes

## Required event output

```json
{
  "event_type": "career.domain_change",
  "start_date": "2012",
  "end_date": null,
  "temporal_precision": "year",
  "location_id": null,
  "organization_id": null,
  "description_normalized": "Moved from academic chemistry to software product work.",
  "confidence": 0.84,
  "evidence_span": "short source span or structured field reference",
  "observable_from": "2012-12-31"
}
```

## Temporal rules

1. If the text says “in the early 1990s”, encode a range, never 1990-01-01.
2. If age is known but calendar date is not, retain age interval and derive date only when birth-date precision permits.
3. If multiple sources disagree, retain competing events/assertions and flag conflict.
4. `observable_from` is the earliest date the information could legitimately be known to a forecaster.
5. Do not let a Wikipedia lead sentence leak final occupation/legacy into a model predicting early adulthood.

## Two-pass extraction

**Pass A — candidate extraction**
High recall; produce atomic facts with evidence.

**Pass B — adjudication**
Deduplicate, resolve ontology labels, score confidence, identify contradictory dates, and assign observability.

LLMs may assist both passes, but every generated event must preserve source provenance and must be auditable.
