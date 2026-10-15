"""R8 dev-only stagewise count-calibration audit for age-only frozen R6 rates.

This audit compares TRAIN-estimated canonical biography-record rates with
previously used VALIDATION person-year counts, not independent people and not
genuinely heldout multi-year trajectories. It cannot establish individual
forecasting ability, person-cluster CIs or survival adjustment.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

DOMAINS={"career":"cc","recognition":"rc","relationship":"lc","other":"oc"}
AGE_BANDS=("18-27","28-37","38-47","48-57","58-67","68-77","78-87")

def audit(model:dict,rows:list[dict])->dict:
    if model.get("protocol")!="minggui-r6-annual-recurrent-lookup-dev-v1" \
       or model.get("label_scope")!="retrospectively_documented_canonical_events_only" \
       or model.get("supported_ages_inclusive")!=[18,87]:
        raise ValueError("requires frozen lifetime R6 documented-event model")
    if model.get("age_bands")!=list(AGE_BANDS):
        raise ValueError("unexpected age partitions")
    if any(r.get("split_name") not in ("train","validation") for r in rows):
        raise ValueError("forbidden split: never include previously examined R4/R5 test rows")
    seen=set()
    for r in rows:
        key=(r["split_name"],r["age_band"],r["hist_band"])
        if key in seen:raise ValueError("duplicate group")
        seen.add(key)
        if r["age_band"] not in AGE_BANDS or r["hist_band"] not in ("0","1","2-4","5+"):
            raise ValueError("unknown bin")
        if int(r["n"])<=0:raise ValueError("empty exposure group")
        for col in DOMAINS.values():
            if not 0<=int(r[col])<=100000:raise ValueError("invalid event counts")
    if len(seen)!=len(rows):raise ValueError("duplicate rows")
    for a in AGE_BANDS:
        if not any(r["split_name"]=="validation" and r["age_band"]==a for r in rows):
            raise ValueError("missing validation age partition")
    output=[]
    val=[r for r in rows if r["split_name"]=="validation"]
    for age in AGE_BANDS:
        sub=[r for r in val if r["age_band"]==age]
        exposure=sum(r["n"] for r in sub)
        by_domain={}
        for domain,col in DOMAINS.items():
            rate=model["age_rates"][age][domain]
            if not math.isfinite(rate) or rate<0:raise ValueError("invalid baseline rate")
            expected=exposure*rate
            actual=sum(r[col] for r in sub)
            ratio=(actual/expected if expected>0 else None)
            # Internal *diagnostic* red flag, NOT a statistical confidence bound.
            warning=expected>=5 and (ratio is None or ratio<.5 or ratio>2)
            by_domain[domain]={
                "actual_documented_records":actual,
                "age_only_expected_documented_records":expected,
                "observed_over_expected":ratio,
                "large_descriptive_mismatch":warning,
            }
        output.append({"age_band":age,"validation_person_years":exposure,"domains":by_domain})
    return {
        "protocol":"r8-r6-dev-stage-calibration-audit-v1",
        "source_snapshot":model["source_snapshot"],
        "validation_person_years":sum(x["validation_person_years"] for x in output),
        "training_person_years":model["train_exposure_person_years"],
        "audit_not_fresh_external_holdout":True,
        "is_multi_year_trajectory_calibrated":False,
        "ready_for_personal_life_forecast":False,
        "engineering_red_flags":sum(
            x["large_descriptive_mismatch"]
            for row in output for x in row["domains"].values()
        ),
        "note":"Per-age retrospective documented-event counts only. No real-life event rates, person-cluster uncertainty, prospective outcomes or long-horizon calibration.",
        "by_age":output,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",type=Path,required=True)
    ap.add_argument("--aggregates",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    result=audit(json.loads(args.model.read_text()),json.loads(args.aggregates.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"person_years":result["validation_person_years"],
                      "red_flags":result["engineering_red_flags"],
                      "ready_for_personal_forecast":False},indent=2))
