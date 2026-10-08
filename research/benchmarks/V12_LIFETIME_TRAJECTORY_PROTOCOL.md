# MingGui lifetime trajectory R6 / v1.2 — preregistration draft and execution gate

**Status: engineering prototype created; no R6 model has been trained and no future-life accuracy is established.**

## Goal

Move from **first documented event within 20 years** (R4/R5) to a **dynamic, recurrent, multi-domain trajectory**. Each year's predicted state should condition on the person's history available at that year. A trajectory is a distribution over possible histories, not a single certain biography.

Concretely:

- Annual multiple-event counts (including 0 and >1), by domain.
- Event order, recency, age-dependent transitions, cross-domain interactions.
- 1/3/5/10/20-year calibrated event probabilities and exploratory age-stage ensembles.
- Recalculation when authentic new history is provided, not fabricated event evidence.
- Clear separation of **latent lived events**, **events recorded in biographies**, and **whether a person was observable**.

## Frozen evidence and feasibility audit (2026-10-08)

Read-only SQL: [v12_recurrent_preflight.sql](v12_recurrent_preflight.sql).

- Source: frozen v1.1 \`7fce3b79-ebfc-40b2-a5f0-e91b28db6a02\`; 36,927 model-eligible canonical facts, **2,448** people with ≥1 such fact of the 3,398 cohort people.
- Across all observed person-years with at least one canonical record: **20,964** person-years; **7,687** had >1 event and **2,281** spanned >1 domain. Therefore a model capped at one event per year is structurally inadequate.
- In the age-18-origin, next-20-year, fully observed-within-Round-5-window audit:

| Split | Eligible person-years | Years with ≥1 documented event | Canonical events | Years with >1 event |
|---|---:|---:|---:|---:|
| Train | 45,527 | 1,578 | 2,527 | 373 |
| Validation | 9,881 | 308 | 461 | 71 |
| Previously seen R5 test (regression only) | 10,443 | 370 | 707 | 137 |

**CRITICAL:** A zero recorded-event year is NOT proof no real event occurred. Wikipedia/Wikidata biographies are selected, retrospective, and incomplete. Above figures characterize *documentation*, not real population event hazards. The old test people have already been used in R4/R5; these are NOT a fresh, untouched R6 test cohort.

## Model specification (to train, not yet trained)

The primary baseline is a **landmarked recurrent-event count model** with yearly domain-specific event intensities \`lambda_d(t | H_<t, X)\`, where \`H_<t\` is an auditable, pre-year history. Multiple domains may occur in the same year. The first simulator uses conditional Poisson draws per domain, with dependence between years introduced by conditioning on simulated earlier events. This is a baseline assumption, not a validated joint distribution.

Controls and ablations:
1. **Population age/cohort prior** (no personal history).
2. **History counts** baseline (same as R5-style aggregates but annual recurrent labels).
3. **Ordered temporal history** (lagged events, last 1/3/5/10 years, time since last domain event, domain transitions, event count dispersion, source confidence and censoring).
4. **Documentation/selection propensity** separately modeled or uncertainty-bounded. Do not treat source silence as an observed negative if adequate coverage is unknown.
5. **BaZi** only as a separately controlled, placebo-tested experimental feature, never auto-weighted positively.

Features must use only events whose \`event_date_max < year_start\`; information visibility must additionally be audited using \`observable_from\` and, where available, actual revision timestamps. Uncertain date intervals straddling year boundaries must be masked or modeled as interval-censored, not assigned an arbitrary point date. Training and evaluation must be **person-disjoint**; do not tune against R4/R5 test results.

## Simulation engine delivered

\`research/models/lifetime_paths.py\`:

- accepts a **future trained/calibrated callable** returning four domain intensities;
- samples multiple events per year, updates history only after completing that year, preventing same-year self-leakage;
- reproducible seeded Monte Carlo pathways;
- age-stage summaries: probability of ≥1 documented event, mean documented event counts;
- refuses negative, infinite, unsupported-domain, and post-cutoff input history;
- **does not** load R5 first-event HGB and **does not** manufacture risk weights from horoscope rules.

\`python -m unittest discover -s tests -p "test_lifetime_paths.py" -v\`

\`python research/models/lifetime_paths.py\` produces an explicitly **synthetic demo only**.

## Evaluation before any release claim

- Primary event-year **log loss / Brier** for occurrence across domains on a genuinely fresh person-disjoint external sample; compare to age-only and history-only controls.
- Yearly count calibration, mean/variance and overdispersion. Compare Poisson to negative binomial, hurdle/zero-inflated or flexible count alternatives on validation data.
- Event-order/time-to-next-event, multi-year count distributions, stagewise calibration and credible coverage. Evaluate multi-event correlations; independent-domain Poisson may fail.
- Observation-model sensitivity analyses across biography coverage, geography, profession and era; prospective time-stamped evidence preferred.
- Bootstrap at **person**, not person-year, level. Frozen metrics, checksums, information-cutoff audit and no test-based hyperparameter selection.
- Exclude single-person celebrity memorization and entity identifiers as predictive features. Historical dataset is not representative of a typical modern user.
- Explicitly report age-range support; do not extrapolate confidently past data support or infer precise mortality, disease, tragedy, or financial fate.

## Gating tasks before official R6 training

1. Freeze a **new v1.2 training materialization** with chronology, date uncertainty, event provenance and adequate observation-window indicator; keep v1.0 and v1.1 immutable.
2. Train an age/cohort + documentation-observation baseline, then recurrent-history model using the **same labeled rows and exact same observation definitions**.
3. Create a fresh external cohort / forward-era and geography holdouts not touched by R4/R5 model selection. Report and archive held-out calibration, not just accuracy.
4. Only connect the simulator to a verified recurrent model; UI must show scenario distributions, source coverage and uncertainty, never “you will definitely...”.

## Scientific motivation

Dynamic landmark models, multistate transition predictions and their calibration have a well-developed methodology. Suggested starting references:
- https://academic.oup.com/ije/article/52/6/1984/7260912
- https://onlinelibrary.wiley.com/doi/10.1002/sim.10094
- https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0320504

**Interpretation:** The current simulator is an infrastructure milestone toward lifetime forecasting, not evidence that lifetime prediction works.
