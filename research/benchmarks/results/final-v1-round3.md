# Final v1 benchmark — Round 3 distribution-shift holdouts

Status: **completed / official**

Round 3 used the exact `hgb_small` nonlinear configuration selected in Round 2. No Round 3 hyperparameter selection was allowed.

## Frozen protocol

- protocol: `next-canonical-domain-generalization-round3-v1`
- dataset: `next-observed-canonical-event-domain / v1.0-final`
- dataset ID: `8261f970-adc3-4f9a-8043-9e0f6cb90be8`
- dataset fingerprint: `a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888`
- model: `HistGradientBoostingClassifier`
- frozen config: `hgb_small`
- learning rate: 0.05
- iterations: 250
- max leaves: 15
- min leaf samples: 30
- L2: 2.0
- seed: 20261006
- no holdout-specific tuning
- validation diagnostic only
- test evaluated once

Workflow run: `37422079918`

## Official artifacts

- forward era: artifact `11393777604`, SHA-256 `77bcb94394f0ae45fb1385dd20bdef30c004a3ed231f466dd4235d1e45eb5da8`
- US holdout: artifact `11393857279`, SHA-256 `4a8edee6979b119ac404479029fa95d9cf7fc2a04026ec9dabbdac799761987d`
- France holdout: artifact `11393842460`, SHA-256 `0b2932d341c169f5eecec3102d69820b0d9f828530dfbec9353851268ccc4061`

## Test macro-F1

| Scenario | History | Raw calendar | BaZi | History + BaZi | Shuffled BaZi |
| --- | ---: | ---: | ---: | ---: | ---: |
| Forward era | **0.4022** | 0.2854 | 0.2557 | 0.3843 | 0.2344 |
| US holdout | **0.4184** | 0.2829 | 0.2598 | 0.3702 | 0.2488 |
| France holdout | **0.3704** | 0.2913 | 0.2844 | 0.3542 | 0.2348 |

History remains the strongest feature family in every distribution-shift scenario.

## Forward-era holdout

Test rows: 2,068  
Test people: 612

| Features | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| History | **0.4022** | **0.4380** | **1.2568** | **0.6723** | 0.1551 |
| Raw calendar | 0.2854 | 0.2942 | 1.5297 | 0.8237 | 0.2174 |
| BaZi | 0.2557 | 0.2582 | 1.5881 | 0.8386 | 0.2280 |
| History + BaZi | 0.3843 | 0.3907 | 1.3333 | 0.7070 | **0.1400** |
| Shuffled BaZi | 0.2344 | 0.2376 | 1.6109 | 0.8440 | 0.2289 |

Paired person-cluster bootstrap:

- History + BaZi − History: `-0.0179`, 95% CI `[-0.0512, +0.0158]`
- BaZi − Raw calendar: `-0.0297`, 95% CI `[-0.0697, +0.0099]`
- BaZi − Placebo: `+0.0213`, 95% CI `[-0.0160, +0.0628]`

No BaZi gate passes.

## US geography holdout

Test rows: 1,637  
Test people: 471

| Features | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| History | **0.4184** | **0.4417** | **1.2689** | **0.6793** | **0.1000** |
| Raw calendar | 0.2829 | 0.2971 | 1.4837 | 0.7964 | 0.1773 |
| BaZi | 0.2598 | 0.2699 | 1.5785 | 0.8313 | 0.2169 |
| History + BaZi | 0.3702 | 0.3763 | 1.3671 | 0.7207 | 0.1425 |
| Shuffled BaZi | 0.2488 | 0.2563 | 1.5826 | 0.8292 | 0.2165 |

Paired person-cluster bootstrap:

- History + BaZi − History: `-0.0482`, 95% CI `[-0.0874, -0.0090]`
- BaZi − Raw calendar: `-0.0231`, 95% CI `[-0.0702, +0.0245]`
- BaZi − Placebo: `+0.0115`, 95% CI `[-0.0354, +0.0578]`

Adding BaZi to history is significantly worse in this holdout.

## France geography holdout

Test rows: 2,271  
Test people: 616

| Features | Macro-F1 | Balanced acc. | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| History | **0.3704** | **0.4029** | **1.3006** | **0.6957** | **0.1341** |
| Raw calendar | 0.2913 | 0.3212 | 1.4621 | 0.7844 | 0.1631 |
| BaZi | 0.2844 | 0.2942 | 1.5181 | 0.8066 | 0.1861 |
| History + BaZi | 0.3542 | 0.3597 | 1.3297 | 0.7029 | 0.1407 |
| Shuffled BaZi | 0.2348 | 0.2376 | 1.5668 | 0.8354 | 0.2246 |

Paired person-cluster bootstrap:

- History + BaZi − History: `-0.0163`, 95% CI `[-0.0465, +0.0138]`
- BaZi − Raw calendar: `-0.0068`, 95% CI `[-0.0445, +0.0321]`
- BaZi − Placebo: `+0.0482`, 95% CI `[+0.0092, +0.0852]`

The true-BaZi versus matched-placebo comparison is positive and its CI does not cross zero in France. This is the only Round 3 holdout where the matched-placebo gate passes.

It does not pass the other two scientific gates:

- BaZi still does not beat raw calendar.
- History + BaZi still does not beat history.

## Raw-domain diagnostic

| Scenario | History | Raw calendar | BaZi | History + BaZi | Shuffled BaZi |
| --- | ---: | ---: | ---: | ---: | ---: |
| Forward era | **0.1893** | 0.1080 | 0.1007 | 0.1653 | 0.0826 |
| US holdout | **0.2386** | 0.1349 | 0.1069 | 0.1619 | 0.1211 |
| France holdout | **0.1932** | 0.1174 | 0.1104 | 0.1798 | 0.0968 |

The finer raw-domain target gives the same broad ordering.

## Combined interpretation

Across person-hash Round 2 plus the three Round 3 distribution-shift tests:

1. **History is consistently the strongest signal.**
2. **Raw birth/calendar consistently outperforms the current BaZi representation.**
3. **History + BaZi does not add stable lift over history.**
4. **True BaZi tends to outperform its shuffled placebo, but the effect is small and inconsistent.**

True BaZi minus placebo:

- person-hash: `+0.0382`, CI crosses zero
- forward era: `+0.0213`, CI crosses zero
- US holdout: `+0.0115`, CI crosses zero
- France holdout: `+0.0482`, CI entirely positive

The France result is interesting but cannot be treated as a general result because the preregistered holdouts must be interpreted together. Three of four nonlinear evaluations do not produce a confidence interval excluding zero.

Even in France, BaZi does not outperform raw calendar and does not add to history. Therefore the current evidence does **not** support treating BaZi as a validated predictive prior.

## What the model does support

The project’s strongest validated component is not traditional fate-reading. It is a data-driven trajectory model built from:

- observed life history;
- age/cutoff state;
- birth/calendar and background controls;
- source-backed canonical events.

This component survives random person splits, era shift, US holdout, and France holdout.

The BaZi layer should remain an experimental low-confidence prior until a later representation or larger corpus demonstrates incremental value beyond raw-calendar and history controls.

## Next modeling implication

Further model-capacity tuning on the same v1.0 test sets should stop here.

The next scientifically useful work is more likely to come from:

1. improving the data representation and event ontology;
2. increasing biography coverage and source diversity in a new snapshot;
3. modeling censoring/time-to-event explicitly instead of classification only;
4. testing sequence/survival models on a new frozen benchmark;
5. treating BaZi as a predeclared auxiliary feature rather than optimizing specifically around the current holdouts.

Any v1.1 data enrichment must create a new immutable snapshot and new benchmark dataset rather than mutate v1.0.
