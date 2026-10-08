"""MingGui R6 DEV baseline: real-data lookup intensities for documented events.

Input: GROUPED train + validation person-years from v12_dev_recurrent_aggregates.sql.
Never accepts old Round 5 test rows. No feature tuning on validation.
Domain rates are expected documented canonical events / person-year.
The model is NOT a rate of every real-life event and should not be marketed as
a general-population lifetime prediction.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

DOMAINS = {"career": ("cp", "cc"), "recognition": ("rp", "rc"),
           "relationship": ("lp", "lc"), "other": ("op", "oc")}
AGES = ("18-24", "25-29", "30-34", "35-37")
LONG_AGES = ("18-27", "28-37", "38-47", "48-57", "58-67", "68-77", "78-87")
HISTORY = ("0", "1", "2-4", "5+")
SHRINKAGE = 200.0  # fixed design constant, NOT selected with validation labels


def age_bin(age: int, *, long: bool = False) -> str:
    if long:
        if 18 <= age <= 87:
            start = 18 + ((age - 18) // 10) * 10
            return f"{start}-{start+9}"
        raise ValueError("long R6 model supports only ages 18..87")
    if 18 <= age <= 24: return "18-24"
    if 25 <= age <= 29: return "25-29"
    if 30 <= age <= 34: return "30-34"
    if 35 <= age <= 37: return "35-37"
    raise ValueError("short R6 model supports only ages 18..37")


def history_bin(count: int) -> str:
    if count < 0: raise ValueError("negative history length")
    if count == 0: return "0"
    if count == 1: return "1"
    return "2-4" if count < 5 else "5+"


def _safe_rate(numer: float, denom: float) -> float:
    if denom <= 0: raise ValueError("invalid denominator")
    return max(0.0, float(numer) / denom)


def fit(rows: list[dict]) -> dict:
    if not rows or any(r["split_name"] not in ("train", "validation") for r in rows):
        raise ValueError("train/validation-only aggregate rows required")
    age_labels = {r["age_band"] for r in rows}
    if age_labels.issubset(set(AGES)):
        bands = AGES
    elif age_labels.issubset(set(LONG_AGES)):
        bands = LONG_AGES
    else:
        raise ValueError("unregistered age band scheme")
    seen = set()
    for r in rows:
        key = (r["split_name"], r["age_band"], r["hist_band"])
        if key in seen: raise ValueError("duplicate group")
        seen.add(key)
        if r["age_band"] not in bands or r["hist_band"] not in HISTORY:
            raise ValueError("unregistered bin")
        if int(r["n"]) < 1: raise ValueError("empty group")
        for pc, cc in DOMAINS.values():
            if not (0 <= int(r[pc]) <= int(r[cc])):
                raise ValueError("positive years exceed events")
            if int(r[pc]) > int(r["n"]):
                raise ValueError("positive years exceed exposure")
    tr = [r for r in rows if r["split_name"] == "train"]
    va = [r for r in rows if r["split_name"] == "validation"]
    if not tr or not va: raise ValueError("both partitions required")

    total = sum(int(r["n"]) for r in tr)
    global_rate = {
        d: _safe_rate(sum(int(r[cc]) for r in tr), total)
        for d, (_, cc) in DOMAINS.items()
    }
    ages = {}
    groups = {}
    for a in bands:
        aged = [r for r in tr if r["age_band"] == a]
        n = sum(int(r["n"]) for r in aged)
        ages[a] = {}
        groups[a] = {}
        for d, (_, cc) in DOMAINS.items():
            # Age-shrunk estimate when few biographies are observed at this age.
            ages[a][d] = _safe_rate(
                sum(int(r[cc]) for r in aged) + SHRINKAGE * global_rate[d],
                n + SHRINKAGE,
            )
        for h in HISTORY:
            g = [r for r in aged if r["hist_band"] == h]
            size = sum(int(r["n"]) for r in g)
            groups[a][h] = {
                d: _safe_rate(
                    sum(int(r[cc]) for r in g) + SHRINKAGE * ages[a][d],
                    size + SHRINKAGE,
                )
                for d, (_, cc) in DOMAINS.items()
            }
    model = {
        "protocol": "minggui-r6-annual-recurrent-lookup-dev-v1",
        "label_scope": "retrospectively_documented_canonical_events_only",
        "source_snapshot": "7fce3b79-ebfc-40b2-a5f0-e91b28db6a02",
        "supported_ages_inclusive": [18, 87] if bands == LONG_AGES else [18, 37],
        "age_bands": list(bands),
        "shrinkage_pseudoyears": SHRINKAGE,
        "train_exposure_person_years": total,
        "age_rates": ages,
        "age_history_rates": groups,
        "history_group_support": {
            a: {h: sum(int(r["n"]) for r in tr
                       if r["age_band"] == a and r["hist_band"] == h)
                for h in HISTORY}
            for a in AGES
        },
    }
    def evaluate(arm: str) -> dict:
        scored = {}
        for domain, (poscol, countcol) in DOMAINS.items():
            loss, brier, reduced_count_nll, exposure, positives, events = (0.,0.,0.,0,0,0)
            for r in va:
                n = int(r["n"])
                observed_positive = int(r[poscol])
                observed_events = int(r[countcol])
                a, h = r["age_band"], r["hist_band"]
                lam = (ages[a][domain] if arm == "age_only"
                       else groups[a][h][domain])
                rate = max(lam, 1e-12)
                prob = min(max(-math.expm1(-lam), 1e-12), 1 - 1e-12)
                loss += (-observed_positive * math.log(prob)
                         -(n - observed_positive) * math.log1p(-prob))
                brier += (observed_positive * (1-prob)**2
                          +(n-observed_positive) * prob**2)
                # Dropped sum(log(y!)), constant between arms on same labels.
                reduced_count_nll += n * rate - observed_events * math.log(rate)
                exposure += n
                positives += observed_positive
                events += observed_events
            scored[domain] = {
                "years": exposure,
                "positive_years": positives,
                "events": events,
                "binary_log_loss": loss / exposure,
                "binary_brier": brier / exposure,
                "count_nll_without_factorial": reduced_count_nll / exposure,
                "predicted_event_rate_units": "documented_events_per_person_year",
            }
        scored["macro_binary_log_loss"] = sum(
            scored[d]["binary_log_loss"] for d in DOMAINS
        ) / len(DOMAINS)
        scored["macro_binary_brier"] = sum(
            scored[d]["binary_brier"] for d in DOMAINS
        ) / len(DOMAINS)
        return scored

    model["dev_validation_metrics"] = {
        "age_only": evaluate("age_only"),
        "age_plus_history": evaluate("age_plus_history"),
    }
    model["interpretation"] = (
        "Validation diagnostics only: neither independent R6 external test nor "
        "person-cluster confidence intervals. Retrospective biography coverage "
        "can mimic individual predictability. Do not use for real-life certainty."
    )
    return model


def intensity_from_model(model: dict, *, age: int, history_count: int) -> dict[str, float]:
    a, h = age_bin(
        age, long=model["supported_ages_inclusive"][1] == 87
    ), history_bin(history_count)
    return dict(model["age_history_rates"][a][h])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("aggregates_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    raw = args.aggregates_json.read_bytes()
    model = fit(json.loads(raw))
    model["input_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(model["dev_validation_metrics"], indent=2))


if __name__ == "__main__":
    main()
