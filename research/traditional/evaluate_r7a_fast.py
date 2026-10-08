"""R7A reduced age-stratified screen. Preregistered *hypothesis*, exploratory fit.

Input is *aggregate only*, frozen SQL output; no licensed birth rows and no
old R4/R5 test persons. This is a simplified fallback after full R7A SQL timed
out. Results do not qualify as confirmation of the full method.
"""
from __future__ import annotations
import hashlib
import json
import math
import sys
from pathlib import Path

SHIFTS=(0,1,3,5)
DOMAINS=("relationship","career")
PSEUDO_YEARS=200
AGE_BANDS=("18-27","28-37","38-47","48-57","58-67","68-77","78-87")


def _ll(n:int, k:int, p:float)->float:
    p=min(1-1e-9,max(1e-9,p))
    return -k*math.log(p)-(n-k)*math.log1p(-p)


def _brier(n:int,k:int,p:float)->float:
    return k*(1-p)**2+(n-k)*p*p


def evaluate(rows:list[dict])->dict:
    seen=set()
    for r in rows:
        key=(r["split_name"],r["age_band"])
        if key in seen or r["split_name"] not in ("train","validation") or r["age_band"] not in AGE_BANDS:
            raise ValueError(f"duplicate or unknown dataset stratum: {key}")
        seen.add(key)
        n=int(r["n"])
        if n<1:raise ValueError("invalid denominator")
        for d in DOMAINS:
            if not 0<=int(r[f"{d}_cases"])<=n:raise ValueError("invalid event count")
        for shift in SHIFTS:
            ne=int(r[f"exposure_{shift}"])
            if not 0<=ne<=n:raise ValueError("invalid exposure")
            for d in DOMAINS:
                k=int(r[f"{d}_{shift}"])
                if not 0<=k<=min(ne,int(r[f"{d}_cases"])):raise ValueError("invalid events in exposed years")
                if int(r[f"{d}_cases"])-k>n-ne:raise ValueError("invalid non-exposed events")
    expected={(sp,a) for sp in ("train","validation") for a in AGE_BANDS}
    if seen!=expected:raise ValueError("incomplete/extra age by split group")
    tr={r["age_band"]:r for r in rows if r["split_name"]=="train"}
    va={r["age_band"]:r for r in rows if r["split_name"]=="validation"}
    out={}
    for d in DOMAINS:
        countname=f"{d}_cases"
        n_train=sum(r["n"] for r in tr.values())
        global_rate=sum(r[countname] for r in tr.values())/n_train
        age_rate={
            a:(r[countname]+PSEUDO_YEARS*global_rate)/(r["n"]+PSEUDO_YEARS)
            for a,r in tr.items()
        }
        domain_arms={}
        for shift in SHIFTS:
            age_loss=interaction_loss=age_brier=interaction_brier=0.0
            denom=positive=exposure=exposed_positive=0
            for age in AGE_BANDS:
                train=tr[age]
                val=va[age]
                prior=age_rate[age]
                train_n1=train[f"exposure_{shift}"]
                train_k1=train[f"{d}_{shift}"]
                train_n0=train["n"]-train_n1
                train_k0=train[countname]-train_k1
                p1=(train_k1+PSEUDO_YEARS*prior)/(train_n1+PSEUDO_YEARS)
                p0=(train_k0+PSEUDO_YEARS*prior)/(train_n0+PSEUDO_YEARS)
                vn1=val[f"exposure_{shift}"]
                vk1=val[f"{d}_{shift}"]
                vn0=val["n"]-vn1
                vk0=val[countname]-vk1
                age_loss+=_ll(val["n"],val[countname],prior)
                interaction_loss+=_ll(vn1,vk1,p1)+_ll(vn0,vk0,p0)
                age_brier+=_brier(val["n"],val[countname],prior)
                interaction_brier+=_brier(vn1,vk1,p1)+_brier(vn0,vk0,p0)
                denom+=val["n"]
                positive+=val[countname]
                exposure+=vn1
                exposed_positive+=vk1
            domain_arms[str(shift)]={
                "validation_person_years":denom,
                "positive_years":positive,
                "exposed_years":exposure,
                "positive_exposed_years":exposed_positive,
                "age_baseline_logloss":age_loss/denom,
                "clash_logloss":interaction_loss/denom,
                "delta_logloss":(interaction_loss-age_loss)/denom,
                "age_baseline_brier":age_brier/denom,
                "clash_brier":interaction_brier/denom,
                "delta_brier":(interaction_brier-age_brier)/denom,
            }
        out[d]=domain_arms
    screen_pass=all(
        out[d]["0"]["delta_logloss"]<0 and
        all(out[d]["0"]["delta_logloss"]<out[d][str(s)]["delta_logloss"] for s in (1,3,5))
        for d in DOMAINS
    )
    return {
        "protocol":"r7a-fast-age-only-exploratory-v1",
        "source_snapshot":"7fce3b79-ebfc-40b2-a5f0-e91b28db6a02",
        "input_split":"train-plus-validation-only",
        "lookup_pseudoyears":PSEUDO_YEARS,
        "shifts":list(SHIFTS),
        "result_by_domain":out,
        "screen_pass":screen_pass,
        "no_external_test":True,
        "birthday_quality":"astro-databank-timed-AA-A-B-selected-only",
        "calendar_limitation":"Gregorian calendar year uses predominant post-LiChun zodiac; Jan-Feb ambiguous",
        "inference_limitation":"Annual age-only exploratory test; R7A prereg full adjusted test SQL timed out; no person-bootstrap or revision-time replay; no DaYun tested",
        "scope":"recorded events in notable historical biographies, not general-population life events",
        "decision":"No BaZi forecast weight from this screening experiment",
    }


def main()->None:
    if len(sys.argv)!=3:
        raise SystemExit("Usage: python evaluate_r7a_fast.py aggregates.json output.json")
    data_bytes=Path(sys.argv[1]).read_bytes()
    raw=json.loads(data_bytes)
    if raw.get("protocol")!="r7a-fast-age-only-exploratory-v1":
        raise ValueError("wrong input version")
    result=evaluate(raw["rows"])
    result["input_sha256"]=hashlib.sha256(data_bytes).hexdigest()
    Path(sys.argv[2]).parent.mkdir(parents=True,exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"screen_pass":result["screen_pass"],
                      "scores":result["result_by_domain"]},indent=2))


if __name__=="__main__":
    main()
