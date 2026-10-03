# MingGui Research Layer

The product is intentionally split into **narrative UX** and **falsifiable modeling**.

## Core experimental question
Does adding traditional Chinese metaphysical features (BaZi-derived features) improve out-of-sample prediction of life-trajectory labels after controlling for ordinary reality variables (era, geography, sex/gender when available, education, family proxies, profession history)?

## Model stack
1. Reality baseline: demographics + historical context only.
2. BaZi-only model: calendar-derived features only.
3. Mixed model: reality + BaZi.
4. Personal calibration: early-life events / questionnaire, only information available before cutoff.
5. Retrieval: nearest historical trajectories using pre-cutoff event embeddings.
6. Long horizon: competing-risk event models + sequence model.

## Non-negotiable evaluation
- Time-based splits, not just random train/test.
- Shuffled-birthday placebo tests.
- Country/era holdout tests.
- No future leakage: predicting age 30-40 means no post-30 features.
- Every public prediction is immutable after creation; outcomes are evaluated later.
- Compare calibration (Brier score / reliability curves), not only accuracy.

## Event ontology
Domains: education, career, migration, relationship, family, finance, health, legal, public-recognition, creative-output, institution, mortality (research-only). Each event stores date precision, source, confidence and whether it was observable before a prediction cutoff.
