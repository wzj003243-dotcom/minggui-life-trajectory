# 命轨 MingGui — Life Trajectory Lab

A public research/art project that treats traditional Chinese fate-reading as a **low-confidence prior**, calibrates it with already-lived events, and eventually combines it with large biographical datasets to produce **probabilistic, testable lifetime trajectory forecasts**.

## Product philosophy

- **Past calibrates; future predicts.** Retrospective fit never counts as a successful prediction.
- **Traditional metaphysics is a feature system, not ground truth.** The data decides whether it adds predictive signal.
- **LLMs narrate; they do not invent probabilities.** Numbers must originate from rule engines, retrieval or trained models.
- **Predictions are immutable.** Every forecast has an information cutoff, horizon, probability and validation rule.
- **No fear-based output.** No deterministic claims about death, disaster, illness, crime, or “you must pay to resolve this”.

## Current state

The web preview already implements:
- BaZi pillar calculation via `lunar-typescript`.
- Traditional element-based prior traits.
- Transparent Bayesian-style calibration from high-information questions.
- Lifetime branch and age-stage UI.
- Research / falsification page.
- Schema for an immutable prediction ledger.
- Wikidata ingestion starter and placebo-birthday test scaffold.

It intentionally **does not pretend to have trained historical-biography weights yet**. The UI marks the cohort layer as unavailable until the research pipeline produces reproducible held-out results.

## Final architecture

`birth → bazi features → traditional prior → early-life calibration → historical trajectory retrieval → multi-event / sequence models → locked prediction ledger → LLM narrative`

## Data strategy

1. **Wikidata (CC0)** for canonical entities and structured person facts.
2. **Pantheon / A Brief History of Human Time** for notable-person benchmarks and cohort construction.
3. **Biography text** for life-event extraction into a strict ontology.
4. **Astro-Databank** only as a high-precision birth-time research source under its current licensing constraints; do not bulk redistribute its licensed export.
5. **CBDB** only under the applicable release/license terms; never expose restricted newer records through a public data service.
6. **Prospective user prediction ledger** becomes the strongest long-term validation set because it is genuinely forward-looking.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Research environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas scikit-learn numpy
python research/ingest/wikidata_people.py
```

## Next research milestones

- Formalize a life-event ontology and leakage policy.
- Create a versioned BaZi feature specification (including hidden stems, seasonal strength, ten gods, relations, dayun/annual features) rather than mixing folk interpretations into raw features.
- Build reality-only and BaZi-only baselines.
- Run shuffled-birthday, era-holdout and geography-holdout tests.
- Train competing-risk event timing models and an event-sequence model.
- Add historical-neighbor evidence cards to the report only after held-out performance is reproducible.
- Deploy the prediction ledger and prospective cohort.
