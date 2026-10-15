"""R7B reproducible *development* comparison: natal context × annual clash.

Reads aggregate counts only, never personal/licensed birth records.
No tuning on validation. Results are NOT a validated future prediction.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

K = 200.0
DOMAINS = ("relationship", "career")
SHIFTS = (0, 1, 3, 5)
ELEMENTS = ("木", "火", "土", "金", "水")
AGES = ("18-27", "28-37", "38-47", "48-57", "58-67", "68-77", "78-87")


def _count(row: dict, col: str) -> int:
    """SQL SUM(...) FILTER returns NULL when no exposed years; interpret as 0."""
    value = row[col]
    if value is None and (col.startswith("relationship_") or col.startswith("career_")):
        return 0
    if value is None:
        raise ValueError("unexpected null in exposure or group count")
    return int(value)


def _metrics(n: int, yes: int, p: float) -> tuple[float, float]:
    p = max(1e-12, min(1 - 1e-12, p))
    return (
        -yes * math.log(p) - (n - yes) * math.log1p(-p),
        yes * (1 - p) ** 2 + (n - yes) * p ** 2,
    )


def score(rows: list[dict]) -> dict:
    if not rows: raise ValueError("empty dataset")
    train, validation = {}, {}
    for row in rows:
        split = row["split_name"]
        if split not in ("train", "validation"):
            raise ValueError("forbidden split, especially old test")
        key = (row["age_band"], row["day_element"], row["natal_month_day_clash"])
        if key[0] not in AGES or key[1] not in ELEMENTS or not isinstance(key[2], bool):
            raise ValueError("unrecognized natal context")
        part = train if split == "train" else validation
        if key in part: raise ValueError("duplicate age/natal group")
        part[key] = row
        n = int(row["n"])
        if n <= 0: raise ValueError("nonpositive exposure")
        for domain in DOMAINS:
            pos = _count(row, f"{domain}_cases")
            if not 0 <= pos <= n: raise ValueError("positive-year count invalid")
            for shift in SHIFTS:
                expo = int(row[f"exposure_{shift}"])
                positive_expo = _count(row, f"{domain}_{shift}")
                if not (0 <= expo <= n and
                        0 <= positive_expo <= min(expo, pos) and
                        pos - positive_expo <= n - expo):
                    raise ValueError("invalid exposed/positive group")
    if set(train) != set(validation):
        raise ValueError("train/validation support mismatch")
    n_val = sum(r["n"] for r in validation.values())
    n_train = sum(r["n"] for r in train.values())
    if n_val <= 0 or n_train <= 0: raise ValueError("no exposure")

    domains = {}
    for domain in DOMAINS:
        key = f"{domain}_cases"
        global_rate = sum(r[key] for r in train.values()) / n_train
        age_rates = {}
        for age in AGES:
            strata = [r for k,r in train.items() if k[0] == age]
            count = sum(r["n"] for r in strata)
            events = sum(r[key] for r in strata)
            age_rates[age] = (events + K * global_rate) / (count + K)
        natal_rates = {
            idx: (row[key] + K * age_rates[idx[0]]) / (row["n"] + K)
            for idx,row in train.items()
        }
        arm_totals = {
            name: [0.0, 0.0]
            for name in ("age_only", "natal_context") + tuple(f"shift_{s}" for s in SHIFTS)
        }
        for idx, val in validation.items():
            t = train[idx]
            age_rate, natal_rate = age_rates[idx[0]], natal_rates[idx]
            for arm, p in (("age_only", age_rate), ("natal_context", natal_rate)):
                ll, br = _metrics(val["n"], val[key], p)
                arm_totals[arm][0] += ll
                arm_totals[arm][1] += br
            for s in SHIFTS:
                exp_t = t[f"exposure_{s}"]
                yes_t = _count(t, f"{domain}_{s}")
                p1 = (yes_t + K * natal_rate) / (exp_t + K)
                p0 = (t[key] - yes_t + K * natal_rate) / (t["n"] - exp_t + K)
                exp_v = val[f"exposure_{s}"]
                yes_v = _count(val, f"{domain}_{s}")
                ll1, br1 = _metrics(exp_v, yes_v, p1)
                ll0, br0 = _metrics(val["n"]-exp_v, val[key]-yes_v, p0)
                arm_totals[f"shift_{s}"][0] += ll1 + ll0
                arm_totals[f"shift_{s}"][1] += br1 + br0
        domains[domain] = {
            arm: {"log_loss": totals[0] / n_val, "brier": totals[1] / n_val}
            for arm, totals in arm_totals.items()
        }
        domains[domain]["validation_positive_years"] = sum(
            r[key] for r in validation.values()
        )
        domains[domain]["validation_person_years"] = n_val
    passed = all(
        domains[d]["shift_0"]["log_loss"] < domains[d]["natal_context"]["log_loss"]
        and all(
            domains[d]["shift_0"]["log_loss"] < domains[d][f"shift_{s}"]["log_loss"]
            for s in (1,3,5)
        )
        for d in DOMAINS
    )
    return {
        "protocol": "r7b-natal-context-annual-clash-dev-v1",
        "snapshot": "7fce3b79-ebfc-40b2-a5f0-e91b28db6a02",
        "train_person_years": n_train,
        "validation_person_years": n_val,
        "k_pseudoyears": K,
        "models": domains,
        "screen_pass": passed,
        "limitations": [
            "No held-out new person sample; old test untouched but previously inspected",
            "Only two natal modifiers and annual proxy, NOT actual DaYun",
            "Uncertainty in Gregorian-vs-LiChun year boundaries",
            "Selected biographies and historical documentation bias",
            "No person-level bootstrap available from aggregate-only rows",
            "No probabilistic forecast weights assigned to traditional symbols",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input_json", type=Path)
    p.add_argument("output_json", type=Path)
    args=p.parse_args()
    raw=args.input_json.read_bytes()
    obj=json.loads(raw)
    if obj.get("protocol")!="r7b-natal-context-annual-clash-dev-v1":
        raise ValueError("invalid aggregate source")
    result=score(obj["rows"])
    result["input_sha256"]=hashlib.sha256(raw).hexdigest()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__=="__main__":
    main()
