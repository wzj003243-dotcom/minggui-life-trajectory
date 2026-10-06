# Final v1 benchmark — Round 3 distribution-shift holdouts

Status: **completed / official**

Round 3 uses the `hgb_small` nonlinear configuration selected in Round 2 and freezes it unchanged across three out-of-distribution splits. No Round 3 validation or test result was used to change model capacity.

## Protocol

- protocol: `next-canonical-domain-generalization-round3-v1`
- dataset: `next-observed-canonical-event-domain / v1.0-final`
- model: Round 2 `hgb_small`
- seed: `20261006`
- feature variants: history, raw calendar, BaZi, history+BaZi, matched shuffled-BaZi
- balanced sample weights: scenario-train labels only
- validation: diagnostic only
- test: evaluated once
- bootstrap: 1,000 replicates clustered by person

Holdouts:

- `forward_era_v1`
- `geo_us_holdout_v1`
- `geo_france_holdout_v1`

## Test macro-F1

| Feature set | Person hash (Round 2) | Forward era | US holdout | France holdout |
| --- | ---: | ---: | ---: | ---: |
| **History reality** | **0.4271** | **0.4022** | **0.4184** | **0.3704** |
| Raw birth calendar | 0.3666 | 0.2854 | 0.2829 | 0.2913 |
| Objective BaZi | 0.2728 | 0.2557 | 0.2598 | 0.2844 |
| History + BaZi | 0.4238 | 0.3843 | 0.3702 | 0.3542 |
| Shuffled-BaZi placebo | 0.2368 | 0.2344 | 0.2488 | 0.2348 |

History is the strongest feature family in every split.

## Forward-era holdout

Test rows: 2,068  
Test people: 612

| Features | Macro-F1 | Balanced acc. | Log loss | ECE |
| --- | ---: | ---: | ---: | ---: |
| **History** | **0.4022** | **0.4380** | **1.2568** | 0.1551 |
| Raw calendar | 0.2854 | 0.2942 | 1.5297 | 0.2174 |
| BaZi | 0.2557 | 0.2582 | 1.5881 | 0.2280 |
| History + BaZi | 0.3843 | 0.3907 | 1.3333 | **0.1400** |
| Placebo | 0.2344 | 0.2376 | 1.6109 | 0.2289 |

Paired person bootstrap:

- History + BaZi − History: **−0.0179**, 95% CI **[−0.0512, +0.0158]**
- BaZi − Raw calendar: **−0.0297**, 95% CI **[−0.0697, +0.0099]**
- BaZi − Placebo: **+0.0213**, 95% CI **[−0.0160, +0.0628]**

No BaZi scientific gate passes.

## US geography holdout

Test rows: 1,637  
Test people: 471

| Features | Macro-F1 | Balanced acc. | Log loss | ECE |
| --- | ---: | ---: | ---: | ---: |
| **History** | **0.4184** | **0.4417** | **1.2689** | **0.1000** |
| Raw calendar | 0.2829 | 0.2971 | 1.4837 | 0.1773 |
| BaZi | 0.2598 | 0.2699 | 1.5785 | 0.2169 |
| History + BaZi | 0.3702 | 0.3763 | 1.3671 | 0.1425 |
| Placebo | 0.2488 | 0.2563 | 1.5826 | 0.2166 |

Paired person bootstrap:

- History + BaZi − History: **−0.0482**, 95% CI **[−0.0874, −0.0090]**
- BaZi − Raw calendar: **−0.0231**, 95% CI **[−0.0702, +0.0245]**
- BaZi − Placebo: **+0.0115**, 95% CI **[−0.0354, +0.0578]**

In this holdout, adding BaZi to history is statistically worse than history alone.

## France geography holdout

Test rows: 2,271  
Test people: 616

| Features | Macro-F1 | Balanced acc. | Log loss | ECE |
| --- | ---: | ---: | ---: | ---: |
| **History** | **0.3704** | **0.4029** | **1.3006** | **0.1341** |
| Raw calendar | 0.2913 | 0.3212 | 1.4621 | 0.1631 |
| BaZi | 0.2844 | 0.2942 | 1.5181 | 0.1861 |
| History + BaZi | 0.3542 | 0.3597 | 1.3297 | 0.1407 |
| Placebo | 0.2348 | 0.2376 | 1.5668 | 0.2246 |

Paired person bootstrap:

- History + BaZi − History: **−0.0163**, 95% CI **[−0.0465, +0.0138]**
- BaZi − Raw calendar: **−0.0068**, 95% CI **[−0.0445, +0.0321]**
- BaZi − Placebo: **+0.0482**, 95% CI **[+0.0092, +0.0852]**

France is the first split where true BaZi significantly outperforms the matched shuffled-BaZi placebo.

However:

- BaZi still does not beat raw birth/calendar;
- BaZi still does not improve history;
- the finer raw-domain metric also remains below history and only slightly below raw calendar.

Therefore this result is evidence of **some non-random structure in the current BaZi representation for the France cohort**, but not evidence that the structure is uniquely astrological or provides incremental life-trajectory information beyond ordinary birth/calendar variables.

## Raw-domain macro-F1

| Feature set | Forward era | US holdout | France holdout |
| --- | ---: | ---: | ---: |
| **History** | **0.1893** | **0.2386** | **0.1932** |
| Raw calendar | 0.1080 | 0.1349 | 0.1174 |
| BaZi | 0.1007 | 0.1069 | 0.1104 |
| History + BaZi | 0.1653 | 0.1619 | 0.1798 |
| Placebo | 0.0826 | 0.1211 | 0.0968 |

The finer target confirms the same overall ordering.

## Combined evidence from Rounds 1–3

Across linear, nonlinear, era-shift, and geography-shift experiments:

### Robust result

**Observed pre-cutoff life history is consistently the strongest predictor of the next documented event class.**

History macro-F1:

- person hash nonlinear: 0.4271
- forward era: 0.4022
- US holdout: 0.4184
- France holdout: 0.3704

This is the strongest empirical support so far for the core MingGui trajectory premise.

### Raw birth/calendar control

Raw calendar beats BaZi in every main 4-class test:

- person hash: 0.3666 vs 0.2728
- forward era: 0.2854 vs 0.2557
- US: 0.2829 vs 0.2598
- France: 0.2913 vs 0.2844

Any future claim for BaZi must therefore continue to control for raw birth/calendar variables.

### True BaZi versus placebo

True BaZi has a positive point estimate versus placebo in all four nonlinear tests:

- person hash: +0.0382
- forward era: +0.0213
- US: +0.0115
- France: +0.0482

Only France has a 95% bootstrap interval entirely above zero.

This pattern is worth retaining as a low-confidence research signal, but it is not robust enough to be promoted to a demonstrated predictive prior.

### Incremental BaZi beyond history

History + BaZi never beats history in macro-F1:

- person hash: −0.0033
- forward era: −0.0179
- US: −0.0482
- France: −0.0163

The US decrement is statistically clear.

The current BaZi representation therefore has **no demonstrated incremental value once lived history is known**.

## Product implication

The evidence supports the original product philosophy:

- treat lived history as the dominant state information;
- treat birth/calendar context as a background prior;
- keep BaZi, if used at all, as a low-confidence experimental prior;
- do not present BaZi as a deterministic engine;
- let observed life events rapidly dominate the posterior as user history accumulates.

This is substantially more defensible than building the product around BaZi and trying to force the data to validate it.

## Artifacts

Forward-era:

- artifact ID: `11393777604`
- SHA-256: `77bcb94394f0ae45fb1385dd20bdef30c004a3ed231f466dd4235d1e45eb5da8`

US holdout:

- artifact ID: `11393857279`
- SHA-256: `4a8edee6979b119ac404479029fa95d9cf7fc2a04026ec9dabbdac799761987d`

France holdout:

- artifact ID: `11393842460`
- SHA-256: `0b2932d341c169f5eecec3102d69820b0d9f828530dfbec9353851268ccc4061`

All three bundles are archived in private `research-artifacts` Storage and registered in `research.artifact_registry`.

Fifteen Round 3 model runs and their validation/test predictions, metrics, bootstrap details, and model artifact references are stored in the private research schema.

## Next modeling priority

Further classification-only attempts to extract BaZi signal are now lower priority.

The next model should focus on the actual life-trajectory problem:

1. use all censor-aware rows rather than only observed-target rows;
2. model **whether and when** the next documented event occurs;
3. model event type/domain as a competing outcome;
4. estimate uncertainty and calibration over future time horizons;
5. condition strongly on observed history;
6. retain raw calendar and BaZi as separately ablated priors.

That moves MingGui from “classify the next recorded event” toward a real probabilistic trajectory engine.
