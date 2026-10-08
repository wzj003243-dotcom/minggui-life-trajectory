"""Run a clearly labeled *research demonstration* of lifetime trajectory paths.

Uses real train-only rates fitted to *retrospectively documented events*.
Not a validated model of the user's actual future or a demographic population.
Run after fitting, never with first-event Round 4/5 HGB probabilities.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fit_recurrent_lookup import intensity_from_model
from lifetime_paths import Event, simulate_paths, summarize_paths, DOMAINS


def stage_bounds(start_age: int, end_age: int) -> tuple[tuple[int, int], ...]:
    edges = [start_age] + [x for x in (30, 40, 50, 60, 70, 80) if start_age < x < end_age] + [end_age]
    return tuple(zip(edges[:-1], edges[1:]))


def run(
    model: dict,
    *,
    from_age: int = 25,
    to_age_exclusive: int = 88,
    history: tuple[Event, ...] = (),
    paths: int = 1000,
    seed: int = 20261008,
) -> dict:
    if model.get("protocol") != "minggui-r6-annual-recurrent-lookup-dev-v1":
        raise ValueError("unsupported recurrent model; do not use R4/R5 first-event hazards")
    if model.get("label_scope") != "retrospectively_documented_canonical_events_only":
        raise ValueError("model label provenance was not verified")
    lo, hi = model["supported_ages_inclusive"]
    if not lo <= from_age < to_age_exclusive <= hi + 1:
        raise ValueError("requested simulation exceeds fitted age range")
    if any(e.domain not in DOMAINS for e in history):
        raise ValueError("unsupported event domain")

    def intensity(state):
        return intensity_from_model(model, age=state.age, history_count=len(state.history))

    outcomes = simulate_paths(
        from_age=from_age,to_age=to_age_exclusive,history=history,
        intensity=intensity,n_paths=paths,seed=seed,
    )
    count_per_path = sorted(len(x) for x in outcomes)
    def quantile(q):
        return count_per_path[int(q * (len(count_per_path) - 1))]
    return {
        "status": "research_simulation_only",
        "label_scope": model["label_scope"],
        "model_protocol": model["protocol"],
        "training_snapshot": model["source_snapshot"],
        "from_age": from_age,
        "to_age_exclusive": to_age_exclusive,
        "not_real_life_guarantee": True,
        "source_observation_bias_not_corrected": True,
        "multi_year_rollout_calibration_not_established": True,
        "sampled_path_count_quantiles_documented_events": {
            "p10": quantile(.10), "median": quantile(.50), "p90": quantile(.90)
        },
        "stagewise_documented_event_probabilities": summarize_paths(
            outcomes, stage_bounds(from_age,to_age_exclusive)
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model",type=Path,required=True)
    ap.add_argument("--from-age",type=int,default=25)
    ap.add_argument("--to-age-exclusive",type=int,default=88)
    ap.add_argument("--paths",type=int,default=1000)
    ap.add_argument("--seed",type=int,default=20261008)
    ap.add_argument("--history-json",type=Path)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    model=json.loads(args.model.read_text())
    raw=json.loads(args.history_json.read_text()) if args.history_json else []
    history=tuple(Event(int(r["age"]),str(r["domain"])) for r in raw)
    result=run(
        model,from_age=args.from_age,to_age_exclusive=args.to_age_exclusive,
        history=history,paths=args.paths,seed=args.seed
    )
    out=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
