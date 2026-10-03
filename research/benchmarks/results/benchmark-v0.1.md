# Benchmark v0.1 — first time MingGui lets BaZi take an exam

## Question

Given a public figure's birth-verified timed chart and only life events observed before age 18/25/30/40, can objective BaZi features improve prediction of the **next observed structured life-event domain**?

Target domains are collapsed to:
- career
- recognition
- relationship
- other

This is intentionally narrower than “predict a whole life.” It is the first falsifiable unit test.

## Cohort

- 3,093 AA/A/B timed births survived Astro-Databank ↔ Wikidata birth-date identity verification.
- 1,645 people had dated structured Wikidata life events.
- 1,634 people produced at least one usable person-cutoff prediction row.
- 5,871 person-cutoff rows.
- A person's rows are kept entirely within train or test in each split.

## Result

| Model | Macro-F1 | Accuracy | Log loss |
|---|---:|---:|---:|
| Reality history | **0.4285 ± 0.0149** | **0.4718** | **1.2053** |
| Reality + compact BaZi | 0.3921 ± 0.0168 | 0.4301 | 1.2480 |
| Compact BaZi only | 0.2692 ± 0.0173 | 0.3050 | 1.3824 |
| Raw birth/calendar | 0.2594 ± 0.0158 | 0.3047 | 1.3433 |

Across 20 repeated person-level splits, Reality + BaZi beat Reality alone **0/20 times**. Average Macro-F1 change: **−0.0364**.

Compact BaZi alone beat raw birth/calendar in 13/20 splits, but only by **+0.0098 Macro-F1 on average**.

## Placebo

Across 5 person splits × 20 decade-stratified birthday/BaZi shuffles:

- BaZi only: real 0.2698 vs shuffled 0.2616 (Δ +0.0082; average percentile 0.63)
- Reality + BaZi: real 0.3994 vs shuffled 0.3889 (Δ +0.0105; average percentile 0.71)

That difference is small and inconsistent. It is not enough to claim validated BaZi signal.

## Current conclusion

**Reality-history features clearly win this first benchmark. We have not demonstrated useful incremental BaZi predictive value yet.**

There is a small hint that real BaZi transformations may contain slightly more structure than raw birth variables or shuffled BaZi, but that hint is much weaker than the penalty introduced when BaZi is added to the reality model.

That could be:
- weak real signal,
- calendar/season/geography confounding,
- public-biography documentation bias,
- sample-size / regularization effects,
- or plain noise.

The project should treat “no signal” as a valid result and keep testing.

## Next falsification tests

1. Forward-era holdout instead of random person split.
2. Geography holdout.
3. Three-pillar vs four-pillar on the same people.
4. Exact event-window binary targets with censoring.
5. Biography-text enrichment to reduce structured-Wikidata sparsity.
6. More placebo permutations and confidence intervals.
7. Compare raw calendar/environment features against BaZi transforms with identical model capacity.
