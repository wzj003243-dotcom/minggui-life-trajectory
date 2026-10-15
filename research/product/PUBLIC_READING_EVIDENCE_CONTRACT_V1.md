# 命轨大众版 v1 — 输入、输出与科学证据边界

**Status:** Frontend implemented and tested. Research preview only. No validated personal fate predictions.

## Public product flow

The public `/analyze` route is a three-step guided intake:

1. **出生资料** — civil birth date; optional city; optional birth time with explicit known/unknown state. No fabricated noon time, DaYun or local timezone correction. If an hour is provided, a provisional symbolic chart may be shown **only as conditional/unverified cultural interpretation**.
2. **重要往事** — up to 30 self-reported events with ages and categories; skip allowed. Validate no event from the future. No private identity fields or source licensing violations.
3. **最关心的未来** — user's focus (career, relationships, learning, home, undecided). This is a presentation preference, **not a probability-changing feature**.

Report sections:

- **人生年表 (Facts)**: only what the user submitted; no retrospective predictions or invented milestones.
- **未来情景 (Scenarios)**: continue existing path, actively change direction, or preserve openness; not ranked or probabilistic until prospective calibration.
- **传统视角 (Symbolic)**: clearly labeled BaZi symbols; no fate/health/wealth certainty, no personal DaYun from unverifiable wall clock.
- **科学依据 (Evidence)**: frozen R6 *age-only* historical documented-event expected counts **per 1,000 biography-person-years**; source and population limitations prominently displayed. The new public reading intentionally does NOT personalize these rates using user's own event count because everyday memory and archival canonical events are not the same measurement process.

Scientific acceptance gates in `tests/public-reading.test.ts`: reject invalid birthdays, no past-event hallucination, no future self-reports, no default hour, no out-of-domain extrapolation, no probabilities, source-independent reference rates and duplicate IDs blocked.

## Model architecture for eventual genuine forecasting

Only after evidence is sufficient:

```
intake (cutoff-stamped and consented)
    -> separated data channels:
       (A) civil-time-birth provenance & uncertainty
       (B) lived experiences with user-verifiable dates
       (C) current context and choices
    -> historical coverage-adjusted event model
    -> independent externally tested time-to-event / recurrent outcomes
    -> calibrated probability interval + provenance + meaningful alternatives
    -> immutable prospective outcome ledger
    -> plain-language life-scroll narration (never changes numeric forecast)
```

**No personal posterior is fitted in the present prototype.** Existing `lib/model.ts` heuristic branch percentages and untested personality mapping have been removed from the public flow; historical R6 descriptive rates are **not** user risk probabilities.

## Product guardrails

- Evidence types displayed distinctly; traditional claims never override data.
- Historical biographies are selective; events that were not documented aren't necessarily absent.
- No birth-time inference by matching known experiences; input uncertainty remains visible.
- No medical, financial, relationship, death-year or guaranteed predictions.
- No input is automatically persisted or transmitted by the new client view.
- Model observations are cutoff-stamped. Whenever a future probability is released, register its issue time, category, target, horizon, confidence interval, exact source/algorithm revision, later outcome evaluation; don't relabel old retrospective fit as prospective success.
- Sensitive field collection should be minimized and comply with retention/consent policies before any network storage is implemented.

## Tests and build

`npm run typecheck && npm test && npm run build`

After green CI, show the product demo for UX review. External validation and calibrating a representative modern cohort are prerequisites for converting scenario cards into honest quantified future predictions.
