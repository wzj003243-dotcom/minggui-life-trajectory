# R7B empirical screen — natal context × annual-branch clash

**Experiment executed:** October 14, 2026.  
**Status:** R7B preregistered development screen **negative**. This is neither an untouched external sample nor a test of full DaYun traditional interaction.  
**Frozen cohort:** v1.1 (`7fce3b79-ebfc-40b2-a5f0-e91b28db6a02`), original age-18 train/validation persons only; previous R4/R5 test sample excluded.

## Method

Pre-outcome specification: [R7B_CONTEXT_INTERACTION_PREREG.md](../R7B_CONTEXT_INTERACTION_PREREG.md).

- 115,288 training and 24,464 validation full Gregorian person-years, ages 18–87, with year-crossing uncertain events masked.
- Targets are **recorded** career and relationship transitions in selected historical biographies, not all actual events.
- Candidate annual-day branch clash against natal day branch. Natal **modifier A:** day-master element (five levels). **Modifier B:** whether natal month/day branches clash (two levels). Combined with age decade gives 7 × 5 × 2 strata per data partition.
- Fit empirical binomial event rate with fixed 200 pseudoyear shrinkage (age → natal context → annual clash). All variants share exactly the same train/validation exposure and label definitions. No model/threshold selection on validation.
- Fixed counterfactual shifted-year placebos +1, +3, +5. The signal is *not* combined with real DaYun in this trial.

## Actual validation results (lower is better)

| Model | Relationship binary log-loss | Career binary log-loss |
| --- | ---: | ---: |
| Age only | **0.05073226** | **0.14576343** |
| Age + day-element + natal month/day clash | 0.05115122 | 0.14622218 |
| Natal context + true annual/day clash | 0.05130034 | 0.14648638 |
| Natal context + shifted +1-year clash | 0.05132780 | 0.14636284 |
| Natal context + shifted +3-year clash | 0.05128252 | 0.14637408 |
| Natal context + shifted +5-year clash | 0.05131905 | 0.14642856 |

The true rule's log-loss was **worse than natal-context baseline in BOTH tested domains**, and two shifted placebo variants were better than the true rule for both domains. Brier also worsened relative to age-only.

- Validation: 816 person-years with targeted career changes and 225 with targeted relationship changes. They may overlap.
- The unadjusted R7A result had a tiny relationship improvement; after adding only *predeclared natal modifiers*, it disappears. The two experiments' differing aggregation and covariates are not strictly matched (do not claim causality from this comparison).
- **Screen gate failed. Zero new traditional predictive weight.** No effect-size significance, individual confidence intervals or external generalization has been demonstrated.

## Input provenance and limitations

1. Gregorian-year majority post-LiChun annual stem/branch is an approximation: historical Jan/early-Feb events are not assigned by their true BaZi-year boundary. Year-only events do not support exact LiChun assignment.
2. The R7B grouping adds two natal modifiers, but **does not include true calculated DaYun**. A full natal × DaYun × annual model remains an untested separate hypothesis.
3. Sampling only birth-time-qualified notable people is highly selected; documentation density, occupation, country, era and biography publication timing confound results.
4. Unknown event documentation does not imply no life event. Temporal observation and censoring models remain incomplete.
5. Validation has been inspected for model development; do not retune rule features against it and call it independent proof. Existing R4/R5 test people are already spent as an untouched test set.
6. No person-level bootstrap is possible from these small published aggregate strata. Longer future path predictions are still scientifically unvalidated.
7. No person-specific licensed Astro-Databank birth facts or identifiable chart rows were exported to the public repository.

## Reproduction and UI

- Locked SQL: [r7b_context_interaction_groups.sql](../r7b_context_interaction_groups.sql)
- Frozen aggregate-only counts: [r7b_context_grouped.json](r7b_context_grouped.json)
- Frozen result: [r7b_validation_scores.json](r7b_validation_scores.json)
- Deterministic evaluator: `research/traditional/evaluate_r7b.py`
- Regression tests: `tests/test_evaluate_r7b.py`
- Symbolic demonstrator: `/research/traditional-demo`, using **fictional technical birth fixture** and real calendar calculation (not real individual's fate).
- GitHub CI: `.github/workflows/research-bazi-interactions.yml`.

```bash
python research/traditional/evaluate_r7b.py \
  research/traditional/results/r7b_context_grouped.json \
  /tmp/r7b.json
npm test
npm run typecheck
npm run build
```

## Next uncompleted gates

Independently reconstruct each person's verified DaYun onset from original time/place, freeze school conventions, generate precisely timed yearly history **without publishing personal birth data**, and then fit properly regularized multiyear interactions with era/geography/profession/coverage controls. Before claiming an incremental gain, require a new never-used external cohort with person-bootstrap confidence bands, source-revision time fidelity and negative shifted-cycle controls. No retrospective tuning of hour, 起运 or rule sign to fit biographies.

**Bottom line:** The work advances the reproducible traditional-method *testing pipeline* and the interactive symbolic **experience**, not the evidence for divinatory accuracy.
