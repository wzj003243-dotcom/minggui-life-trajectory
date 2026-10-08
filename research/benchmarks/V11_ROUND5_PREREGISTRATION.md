# v1.1 Round 5 preregistration — matched history lift

**Frozen before training/test evaluation.**

Source snapshot `7fce3b79-ebfc-40b2-a5f0-e91b28db6a02` (status `frozen`, canonical SHA-256 `2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf`).

This is the **first v1.1 comparative training experiment**. It is **not** a claim that the full trajectory model has been retrained and deployed.

## Comparable derived data

- Cutoff rows: **13,064**; person membership exactly inherited from frozen v1.0 Round 4.
- Censoring windows: copied from v1.0 and never extended.
- Person split: frozen `person_hash_v1`; no person crosses partitions.
- History facts: rebuilt using the same aggregate SQL for both arms, from the v1.0 or v1.1 frozen canonical snapshots, only when `observable_from <= information_cutoff` and `event_date_max <= information_cutoff`.
- Targets: earliest v1.1 canonical event observed after the information cutoff, up to the frozen observation end; only `snapshot_model_eligible` facts. All comparisons use **these same v1.1 labels**.
- Risk grid: intervals 0–1, 1–3, 3–5, 5–10, 10–20 years. Stop after the first event; omit partially censored intervals.
- Derived rows: **49,909** person-period examples; **7,283** observed-event intervals.
- Derivation SQL: `supabase/v11_round5_matched.sql`.
- No v1.0 or v1.1 source snapshot is modified.

## Preselected arms

1. `old_history_recomputed`: history-only feature values recomputed from v1.0 canonical snapshot using the exact same SQL and controls as the new arm.
2. `v11_history_recomputed`: history-only feature values recomputed from v1.1 canonical snapshot.
3. `interval_empirical_prior`: fit from training portion only, interval index.

Both HGB models use fixed Round 4 `hgb_small` configuration: learning rate 0.05; iterations 250; max leaf nodes 15; minimum leaf samples 30; L2 penalty 2.0; early stopping off, seed 20261006, no class weights or tuning. Features follow Round 4's `history_reality_v1` feature family (no BaZi or raw-calendar variant selected using test outcomes).

For both arms, unchanged birth background/time and cutoff features are taken from the same frozen v1.0 feature snapshot, while history event counts/domain counts are recomputed independently under the respective frozen source snapshot.

## Outcomes and decision

Primary held-out **test** outcome is interval multiclass log loss, with Brier score and event-vs-no-event Brier as companion calibration diagnostics. Secondary macro-F1, conditional event-domain log loss and 1/3/5/10/20 year cumulative-incidence diagnostics.

Report paired delta `v11_history - old_history` with 1000 person-cluster bootstrap resamples over identical rows (negative delta favors v1.1). Also report by cutoff history sparsity. Do not use test feedback to tune.

**Cautions:** Predicts first *documented* canonical life event, not actual destiny. Later-published biographies retrospectively document historical events; this is not a strict real-time historical replay. Frozen observation windows avoid artificial follow-up extension but inherit v1.0 observation-coverage bias. Full v1.1 BaZi vs placebo tests remain future work.
