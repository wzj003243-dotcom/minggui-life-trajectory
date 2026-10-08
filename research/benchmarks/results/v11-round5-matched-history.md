# MingGui v1.1 Round 5 — matched-history trajectory benchmark

**Status:** Completed, evaluated on the held-out test persons, immutable experiment ZIP archived in private Supabase Storage.

## Scientific question

When the target is **the next documented canonical life event** from the newly frozen v1.1 source, does using the richer **v1.1 pre-cutoff history** improve calibrated probabilistic trajectory prediction relative to the same model given the same person's v1.0 pre-cutoff history?

This is a **matched-label, matched-person** comparison. It is **not** a comparison of raw v1.0 Round 4 log-loss with v1.1 Round 5 log-loss, because the target labels and risk sets changed.

## Immutable data and execution

- Frozen v1.1 source snapshot: `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`
- v1.1 canonical fingerprint SHA-256: `2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf`
- Matched hazard training dataset: `36486fe4-a961-4f84-b3ee-11bdf978ea1b`
- Matched training dataset fingerprint: `fb8f6be67a5dba22a3bc3fdbf2f799f946c5755a2b08d44528138fd88b8e6443`
- Training source code: `research/models/benchmark_v11_round5.py`
- Label/feature construction: `supabase/v11_round5_matched.sql`
- Pre-registration: `research/benchmarks/V11_ROUND5_PREREGISTRATION.md`
- Training GitHub Actions run: `37747038831` (**success**), code commit `95977ced16a2d3878ab1fb1ee5b6fef578297fc0`
- Import/archive GitHub Actions run: `37747822725` (**success**)
- GitHub artifact ID: `11536022737`
- Exact ZIP SHA-256: `7df20c54887b76094f4d3428b227b623d779aea35644a3d4925aa1296749f00a`
- Private storage: `research-artifacts/model-runs/v11-round5/7df20c54887b76094f4d3428b227b623d779aea35644a3d4925aa1296749f00a/bundle.zip`
- Frozen sklearn version: `1.9.1`; NumPy `2.5.3`; Python `3.12.14`

The source ZIP includes both fitted HGB joblib models, full validation/test interval prediction probabilities, 1/3/5/10/20-year cumulative incidence predictions, interval and horizon metrics, bootstrap results, input SHA hashes and model manifests. Results were registered as **three model runs, 164 model metric records**, and model artifact references. The archive endpoint was re-locked to JWT-required after importing.

## Matched cohort

- Same 13,064 person-cutoff observations and fixed v1.0 person-level train/validation/test splits
- Training: **2,339 people**; validation: **506**; held-out test: **537**
- Censor-aware v1.1 target/risk set: **49,909** labeled person-period intervals, including **7,283** first-event intervals
- Test: **8,124** comparable interval rows from 537 persons
- Feature counts changed in **2,424** cutoff observations; new domain counts changed in 2,425.
- Next canonical event IDs changed in **2,349** cutoff observations; **1,200** were newly observed targets where v1.0 had none.

**No test-driven tuning:** both HGB arms use Round 4's fixed `hgb_small`: learning_rate=0.05, max_iter=250, max_leaf_nodes=15, min_samples_leaf=30, l2_regularization=2.0, no early stopping or class weights, seed=20261006. Interval prior trained on training split only.

## Main test results

All metrics below use **the same v1.1 true labels**. Lower log-loss and Brier are better.

| Arm | Test N | Interval log-loss | Multiclass Brier | Event-vs-no-event Brier | ECE (10 bins) | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| Interval prior | 8,124 | 0.559036 | 0.244608 | 0.115173 | 0.014250 | 0.185406 |
| HGB, old history | 8,124 | **0.493647** | 0.225379 | 0.104241 | **0.006912** | **0.247224** |
| HGB, v1.1 history | 8,124 | 0.493695 | **0.225153** | **0.103897** | 0.006930 | 0.239974 |

Conditional event-domain log-loss: **1.070583** (old) versus **1.089486** (new).

### Primary paired, person-cluster bootstrap (1,000 resamples)

`v1.1 history minus old history`:

- **Log-loss difference: +0.0000473**, 95% CI **[-0.004080, +0.004016]**.
- **Multiclass Brier difference: -0.0002263**, 95% CI **[-0.001935, +0.001547]**.
- Paired people: **537**; paired intervals: **8,124**.
- Both confidence intervals cross zero: **no stable overall advantage for either history arm**.

### Validation-only diagnostic

| Arm | Validation log-loss | Brier |
|---|---:|---:|
| Interval prior | 0.581371 | 0.255153 |
| Old history | 0.519153 | 0.234478 |
| v1.1 history | **0.504507** | **0.229751** |

v1.1 improves validation but not the held-out test. This discordance cautions against selecting a new, more complex system on validation alone.

### Test cumulative horizon log-loss

| Horizon | Old history | v1.1 history |
|---|---:|---:|
| 1 year | 0.302583 | **0.302090** |
| 5 years | 0.753417 | **0.750023** |
| 10 years | 0.990991 | **0.985258** |
| 20 years | **1.197836** | 1.198804 |

These are descriptive; no horizon-specific confidence interval was preregistered in the first v1.1 run.

## Prespecified baseline-history sparsity diagnostics

Person-clustered bootstrap of `v1.1 - old` interval log-loss within baseline cutoff-history strata:

| v1.0 historical canonical event count | Test interval rows | Delta log-loss | Bootstrap CI95 |
|---|---:|---:|---|
| 0 | 6,607 | **-0.003670** | [-0.007585, -0.000019] |
| 1 | 719 | +0.017796 | [+0.000379, +0.038876] |
| 2–4 | 449 | +0.015851 | [-0.015591, +0.046478] |
| 5+ | 349 | +0.013513 | [-0.020616, +0.044382] |

The zero-history stratum suggests a possible useful niche for the new source enrichment, while the one-event group trends the other way. **The stratum confidence intervals were not multiplicity-adjusted,** and historical cutoffs from the same person can appear in several strata; these results do **not** establish a generalizable subgroup advantage. Test-person reuse for exploratory analysis makes any subsequent targeted optimization requiring fresh held-out confirmation.

## Interpretation and decision

1. History is consistently more useful than an interval-only prior on this dataset.
2. v1.1 substantially improved **coverage and label completeness** (347 people formerly with zero eligible events gained evidence at the source-snapshot level), but the frozen-capacity HGB did **not** translate that into a statistically stable overall test-log-loss gain.
3. The new event-rich corpus may need features that express **event order, recency, duration, source reliability and domain transitions**, not just static counts, to exploit its increased information density.
4. Future work should also test whether year-precision narrative extraction creates target ambiguity and observation-process bias; a multi-source adjudication or observation model may matter more than increasing booster capacity.
5. **No new evidence for BaZi** was produced by this two-arm Round 5 experiment. Prior no-lift conclusions remain unchanged pending a properly controlled follow-on test.
6. Continue with a **separate preregistered feature-design study** and forward-era/geographic external validity checks. Do not tune against or reuse this test split for model selection.

## Limitations

Predicted target is the next **documented** canonical event, not a real-life guarantee. Historical biographies can be written retrospectively; source publication timestamp is not the same as historical event observability, and this is not a real-time historical prospective validation. Observation windows are copied from frozen v1.0 for comparability and therefore do not eliminate uneven biography completeness. The dataset samples notable historical people, not representative lives.

This result file and its exact artifact digest are the immutable evaluation record; any future experiment must use a new run/dataset version and preserve the Round 5 test predictions.
