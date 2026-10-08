"""Experimental recurrent-event life-trajectory Monte Carlo engine.

This is a *mechanism*, not a validated predictive model. Annual intensities
must come from a separately fitted and calibrated landmark/recurrent-event
model. Do not feed next-FIRST-event HGB probabilities to this API: doing so
would misinterpret first-event risks as recurrent-event rates.

No deterministic fate, mortality inference, or synthetic certainty is produced.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp, isfinite
from random import Random
from typing import Callable, Mapping

DOMAINS = ("career", "recognition", "relationship", "other")


@dataclass(frozen=True)
class Event:
    age: int
    domain: str


@dataclass(frozen=True)
class State:
    age: int
    history: tuple[Event, ...]

    def count(self, domain: str, last_n_years: int | None = None) -> int:
        return sum(
            e.domain == domain and
            (last_n_years is None or e.age >= self.age - last_n_years)
            for e in self.history
        )


AnnualIntensity = Callable[[State], Mapping[str, float]]


def _poisson(rng: Random, rate: float) -> int:
    # Bounded annual rates avoid numerical underflow and unreasonably long loops.
    if rate == 0:
        return 0
    product = 1.0
    threshold = exp(-rate)
    k = 0
    while product > threshold:
        k += 1
        product *= rng.random()
    return k - 1


def _checked_rates(value: Mapping[str, float]) -> dict[str, float]:
    if set(value) != set(DOMAINS):
        raise ValueError(f"annual intensity must contain exactly {DOMAINS}")
    out: dict[str, float] = {}
    for name in DOMAINS:
        rate = float(value[name])
        if not isfinite(rate) or rate < 0 or rate > 10:
            raise ValueError(f"invalid annual expected event count for {name}: {rate}")
        out[name] = rate
    return out


def simulate_paths(
    *,
    from_age: int,
    to_age: int,
    history: tuple[Event, ...],
    intensity: AnnualIntensity,
    n_paths: int = 1000,
    seed: int = 20261008,
) -> list[tuple[Event, ...]]:
    """Generate observed-domain paths for ages [from_age, to_age).

    Same-year events are an unordered multiset. Model callback sees only
    past years, never simulated events later within its current year.
    Event rows already in history are never returned as predictions.
    """
    if not (0 <= from_age < to_age <= 120):
        raise ValueError("ages must satisfy 0 <= from_age < to_age <= 120")
    if n_paths < 1 or n_paths > 100000:
        raise ValueError("n_paths out of supported range")
    if any(e.age >= from_age or e.age < 0 or e.domain not in DOMAINS for e in history):
        raise ValueError("history must contain only recognized pre-cutoff events")
    rng = Random(seed)
    paths = []
    for _ in range(n_paths):
        known = list(history)
        future = []
        for age in range(from_age, to_age):
            rates = _checked_rates(intensity(State(age=age, history=tuple(known))))
            batch = [Event(age, d) for d in DOMAINS for _ in range(_poisson(rng, rates[d]))]
            future.extend(batch)
            known.extend(batch)
        paths.append(tuple(future))
    return paths


def summarize_paths(paths: list[tuple[Event, ...]], stages: tuple[tuple[int, int], ...]) -> dict:
    """Aggregate probabilities of >=1 documented event, not life guarantees."""
    if not paths:
        raise ValueError("paths cannot be empty")
    if any(lo >= hi for lo, hi in stages):
        raise ValueError("stage boundaries must increase")
    result = {"n_paths": len(paths), "stages": []}
    for lo, hi in stages:
        counts = [Counter(e.domain for e in path if lo <= e.age < hi) for path in paths]
        result["stages"].append({
            "age_from": lo,
            "age_to_exclusive": hi,
            "domains": {
                d: {
                    "probability_at_least_one": sum(c[d] > 0 for c in counts) / len(paths),
                    "mean_documented_events": sum(c[d] for c in counts) / len(paths),
                } for d in DOMAINS
            },
            "mean_all_documented_events": sum(sum(c.values()) for c in counts) / len(paths),
        })
    return result


if __name__ == "__main__":
    # Demonstration ONLY: artificial rates are not MingGui model estimates.
    import json
    demo = lambda state: {
        "career": 0.08 + 0.02 * (state.count("career") == 0),
        "recognition": 0.02,
        "relationship": 0.04,
        "other": 0.03,
    }
    paths = simulate_paths(from_age=25, to_age=85, history=(), intensity=demo, n_paths=500, seed=7)
    print(json.dumps({"status": "synthetic_demo_only", **summarize_paths(paths, ((25, 40), (40, 60), (60, 85)))}, indent=2))
