# Gold 300 validation cohort

Before scaling biography extraction to tens of thousands of people, MingGui keeps a manually/adjudicated validation cohort.

## Target

300 people selected across as many available combinations of:
- geography
- occupation
- birth era
- gender
- Wikipedia coverage tier

For each person, aim for 20–50 source-backed life events across multiple domains and life stages.

## What is scored

1. Candidate extraction recall: did the pipeline surface the sentence containing a real event?
2. Event precision: was the proposed candidate actually a life event?
3. Domain accuracy: education / career / migration / creation / recognition / relationship / setback...
4. Temporal accuracy: exact year/date/range extracted correctly.
5. Identity accuracy: evidence belongs to the intended person.
6. Deduplication accuracy: same event from multiple sources is merged without erasing provenance.

## Minimum target before large-scale text extraction

- event precision >= 0.90
- domain accuracy >= 0.90
- date/range accuracy >= 0.95
- identity accuracy >= 0.995

The Gold set is not a model training set by default. It is an extraction/evaluation set.
