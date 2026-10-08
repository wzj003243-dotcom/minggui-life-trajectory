# R7 — Traditional inference as a compositional, testable method

**Status:** engineering research hypothesis, not an empirically supported BaZi life forecaster. The earlier Round 4 BaZi results remain negative or inconclusive. No predictive weights were trained in this phase.

## Central distinction

Old test: use static birth-derived BaZi fields as features.
New hypothesis: the predictive unit may be a *rule-based conjunction* of natal chart, DaYun, annual GanZhi, age and the person's history. The conjunction needs its own scientific validation rather than presuming traditional rules work.

Birth evidence → verified natal pillars → Ten Gods / hidden stems / seasonal reference → verified DaYun and annual pillars → traceable interactions → predeclared, observable event hypotheses → external held-out calibration → immutable future prediction ledger.

## Implementation

- research/traditional/bazi_composition_v1.py builds descriptive symbolic records for natal pillars, Ten Gods, hidden stems, stem combinations, branch six combinations and six clashes.
- Every relation records source and target pillars, symbolic type and matched signs. A match does NOT imply good or bad fortune or a life event.
- An unknown hour stays absent. DaYun start age must be supplied by an independently verified calendar method. No retrospective choice of lucky hour or luck-cycle onset based on biography.
- The module never calculates horoscope probabilities; it emits prediction_probability: null and event mapping: unassigned_until_preregistered.
- Calendar evidence must include historical local timezone and birthplace precision, seasonal-term year boundary (e.g. Li Chun convention), day-boundary convention, sect and library version; keep alternatives when uncertain.
- Existing lib/bazi.ts and pinned lunar-typescript package already perform pillars. Verify installed 1.8.6 APIs for EightChar / Yun / DaYun when adding the dynamic converter; do not hand-wave a 10-year interval.

## Candidate hypotheses to register BEFORE touching outcomes

| Hypothesis | Traditional-symbol conjunction | Outcome candidate | Caveat |
|---|---|---|---|
| H1 | Annual branch clashes natal day branch | Relationship / other life-state transition in specified following interval | No predetermined good/bad or guarantee |
| H2 | Both luck and annual stems carry 官/杀 Ten Gods | Career position change / appointment | Job and era reporting are confounders |
| H3 | DaYun and annual pillars are identical (岁运并临) | General transition intensity differs from controls | Neutral direction, sparse base rate |
| H4 | Full graph of natal × luck × annual interactions | Incremental log-loss vs additive symbols | Need a genuinely new person-disjoint test |

These are **candidate** event mappings for expert/source review, NOT validated predictions. Reject undefined labels, retroactive edits and vague statements such as 'something important will happen'.

## Predeclared ablation ladder

1. Age + observable life-history + documentation-coverage controls (strong R6 baseline).
2. Same + raw year/month/day/hour/locality and smooth calendar-era controls.
3. Same + static natal BaZi.
4. Same + dynamic DaYun/annual symbols without interactions.
5. Same + additive natal and dynamic symbols.
6. Same + explicitly encoded natal × cycle interactions.
7. Pre-specified rule-card engine, only if reproducible across independent practitioners.

Use: matched birth-era/geographic shuffled charts, one/three/five-year shifted cycles, raw-calendar and cyclical placebo encodings. Each system derived from the same date is correlated and cannot count as independent confirmation. The traditional layer only influences actual forecast probabilities if incrementality passes untouched external cohort evaluation.

## Different traditions are NOT automatically complementary evidence

- BaZi: first internally consistent experimental family; freeze each named school and its relation rules separately.
- Zi Wei Dou Shu: separate birth-hour-dependent model and separate benchmark, then compare with BaZi and raw calendar.
- 六爻/奇门 question-specific casting: would require independently timestamped PRE-outcome questions/cast records, never reconstruct casts after learning an event.
- Feng Shui, physiognomy and other observation-based methods require consent, defined evidence collection and privacy review; do not invent measurements.

## Protocol and bias gates

- Prior Round 4/5 tests have been inspected and cannot become a new untouched external test set.
- Historical biography silence is not absence of a real event; high-production celebrities distort frequencies.
- Missing birth hour is a mixture of legitimate chart possibilities, not permission to pick the best-fitting hour. If estimating possible alternatives, choose weights before labels, keep a sensitivity range.
- Multiple-comparison control for H1–H4; evaluate proper scoring rules (log-loss/Brier), stagewise and long-path calibration, and person-cluster bootstrap.
- Cross-era, geography and occupation holdouts plus timestamp-accurate historical publication availability are needed.
- Retrospective calibration must never be reported as successfully predicting a person's past. New prospective prediction ledgers should lock date, horizon, frozen rule version, probability and verifiable truth definition.
- '命局强弱/喜用神/格局/神煞' have multiple conventions; add only as versioned school-specific algorithms with tested reproducibility, not as intuition or free-form LLM labels.

## Reproduction and scope

Unit tests: python -m unittest discover -s tests -p 'test_bazi_composition.py' -v

Current artifact is symbolic rule infrastructure plus a research protocol. It does not establish whether traditional BaZi produces incremental predictive accuracy.