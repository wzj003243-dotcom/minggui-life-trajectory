# Architecture — 命轨 MingGui

## 1. Product contract

MingGui is a **probabilistic lifetime trajectory simulator** with a traditional Chinese metaphysics prior. It must preserve the emotional/ritual quality of a “命书” while keeping the predictive core inspectable and falsifiable.

### Hard separation
- `calculation`: calendar / BaZi features, deterministic and versioned.
- `tradition`: rules from named schools/texts, each with provenance and version.
- `calibration`: observed past events and user answers; may update person-level posterior, but never earns prediction credit.
- `cohort`: historical biography retrieval and learned population statistics.
- `forecast`: only uses information available before an immutable cutoff.
- `narrative`: LLM turns structured evidence into readable prose; it cannot invent scores or probabilities.

## 2. Runtime path

```text
Birth Input
  ↓
Calendar Normalization ── timezone / solar terms / time precision
  ↓
BaZi Feature Vector ── pillars / stems / branches / hidden stems / ten gods / relations / cycles
  ↓
Traditional Prior ── hypotheses + low confidence
  ↓
Past Calibration ── life events + high-information questionnaire
  ↓
Personal State Vector
  ↓
Historical Retrieval ── nearest pre-cutoff trajectories
  ↓
Trajectory Models ── archetype + competing risks + event sequence
  ↓
Forecast Composer ── branches / ages / hinges / probabilities
  ↓
Prediction Ledger ── immutable timestamp + validation rule
  ↓
Narrative Renderer
```

## 3. Lifetime forecast object

Each forecast should contain:
- `information_cutoff`
- `birth_data_precision`
- `tradition_version`
- `model_version`
- `life_branch[]` with normalized probabilities
- age-window predictions (not exact-date fortune-telling by default)
- `evidence`: contribution from tradition / reality / behavior / historical cohort
- `hinges`: user-controllable decisions that change branch probabilities
- `validation_rules`
- `uncertainty_notes`

## 4. Model family

### Layer A — traditional prior
Bayesian prior or log-odds adjustments generated from a transparent rule table. No free-form LLM inference.

### Layer B — reality baseline
Gradient boosting / regularized linear models using ordinary predictors: era, geography, education, occupation history, mobility, public family proxies, etc.

### Layer C — historical trajectory
- multi-class archetype classifier
- competing-risk survival model for event windows
- sequence model over standardized life-event tokens
- nearest-neighbor retrieval for human-readable evidence

### Layer D — mixed model
Test whether BaZi-derived features add out-of-sample predictive signal beyond the reality baseline. If they do not, the product must say so.

## 5. Model registry

Every released model stores:
- training cohort snapshot hash
- feature schema version
- rulebook version
- source-license manifest
- train/validation/test time windows
- metrics and calibration plots
- placebo-birthday distribution
- known failure modes

## 6. Safety / epistemic rules

- Do not output deterministic medical, death, crime, disaster, or financial predictions.
- Do not use “化解付费” or fear-based upsells.
- Do not infer sensitive personal facts from public prediction output.
- Give users deletion/export control for private life-event timelines.
- Keep research-only sensitive targets separate from user-facing output.
