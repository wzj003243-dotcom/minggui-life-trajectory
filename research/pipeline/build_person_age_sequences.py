"""Build person-age sequence examples for trajectory / survival modeling.

This avoids treating missing Wikidata events as confirmed negatives. Each row is a person at
an information cutoff age and contains:
- objective BaZi features
- ordinary reality baseline variables
- observed past event counts
- next observed event type/time
- right-censor age based on death/current follow-up

The downstream model may use competing-risk survival / sequence objectives.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

CUTS=(18,25,30,40)

def read_csv(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        yield from csv.DictReader(f)

def fnum(x):
    try:return float(x)
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bhht_sample")
    ap.add_argument("event_cohort")
    ap.add_argument("bazi_features")
    ap.add_argument("life_events")
    ap.add_argument("output")
    ap.add_argument("--as-of-year",type=int,default=2026)
    args=ap.parse_args()

    bhht={r["wikidata_code"]:r for r in read_csv(Path(args.bhht_sample))}
    event_ids={r["wikidata_id"] for r in read_csv(Path(args.event_cohort))}
    bazi={str(r["person_id"]):r for r in read_csv(Path(args.bazi_features))}

    events=defaultdict(list)
    event_types=set()
    for e in read_csv(Path(args.life_events)):
        pid=e["person_id"]
        if pid not in event_ids:continue
        ages=[fnum(e.get("age_point")),fnum(e.get("age_start")),fnum(e.get("age_end"))]
        age=next((x for x in ages if x is not None),None)
        if age is None or age < 0:continue
        x={"age":age,"event_type":e["event_type"],"confidence":fnum(e.get("confidence")) or 0}
        events[pid].append(x);event_types.add(e["event_type"])
    event_types=sorted(event_types)

    base_fields=[
      "person_id","cutoff_age","birth_year","death_year","censor_age","followup_after_cutoff",
      "gender","level1_main_occ","level2_main_occ","level3_main_occ","un_region","un_subregion",
      "number_wiki_editions","sampling_weight","past_event_total","next_observed_event_type",
      "next_observed_event_age","next_observed_event_delay","next_observed_event_confidence"
    ]
    bazi_fields=[]
    if bazi:
        sample=next(iter(bazi.values()))
        bazi_fields=[k for k in sample if k not in {"person_id"}]
    past_fields=[f"past_count__{x}" for x in event_types]
    fields=base_fields+past_fields+[f"bazi__{x}" for x in bazi_fields]

    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=people=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid in sorted(event_ids):
            meta=bhht.get(pid);bf=bazi.get(pid)
            if not meta or not bf:continue
            by=fnum(meta.get("birth"));dy=fnum(meta.get("death"))
            if by is None:continue
            censor=(dy-by) if dy is not None else (args.as_of_year-by)
            if censor < 0:continue
            pe=sorted(events.get(pid,[]),key=lambda x:x["age"])
            people+=1
            for cutoff in CUTS:
                if censor <= cutoff:continue
                past=[e for e in pe if e["age"]<=cutoff]
                future=[e for e in pe if e["age"]>cutoff]
                nxt=future[0] if future else None
                counts=Counter(e["event_type"] for e in past)
                row={
                  "person_id":pid,"cutoff_age":cutoff,"birth_year":int(by),
                  "death_year":int(dy) if dy is not None else "",
                  "censor_age":round(censor,3),"followup_after_cutoff":round(censor-cutoff,3),
                  "gender":meta.get("gender"),"level1_main_occ":meta.get("level1_main_occ"),
                  "level2_main_occ":meta.get("level2_main_occ"),"level3_main_occ":meta.get("level3_main_occ"),
                  "un_region":meta.get("un_region"),"un_subregion":meta.get("un_subregion"),
                  "number_wiki_editions":meta.get("number_wiki_editions"),
                  "sampling_weight":meta.get("sampling_weight"),
                  "past_event_total":len(past),
                  "next_observed_event_type":nxt["event_type"] if nxt else "",
                  "next_observed_event_age":round(nxt["age"],3) if nxt else "",
                  "next_observed_event_delay":round(nxt["age"]-cutoff,3) if nxt else "",
                  "next_observed_event_confidence":nxt["confidence"] if nxt else ""
                }
                for et in event_types:row[f"past_count__{et}"]=counts[et]
                for k in bazi_fields:row[f"bazi__{k}"]=bf.get(k,"")
                wr.writerow(row);rows+=1

    report={
      "people_with_examples":people,"person_age_rows":rows,"cutoffs":list(CUTS),
      "event_types":event_types,"label_semantics":"next_observed_event_with_right_censoring",
      "warning":"absence of a Wikidata event is not treated as a confirmed negative"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
