"""Build leakage-safe person-age rows for the timed cohort.

Unlike the public BHHT sequence builder, this uses only birth-fixed covariates and past dated
events. It never uses final occupation/notability as a predictor.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import Counter,defaultdict
from pathlib import Path

CUTS=(18,25,30,40)

def read(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def num(x):
    try:return float(x)
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("linked");ap.add_argument("events");ap.add_argument("output")
    args=ap.parse_args()
    people={r["wikidata_id"]:r for r in read(Path(args.linked))}
    events=defaultdict(list);types=set()
    for e in read(Path(args.events)):
        amin=num(e.get("age_min"));amax=num(e.get("age_max"));amid=num(e.get("age_mid"))
        if amin is None or amax is None or amid is None or amax<0:continue
        x={"age_min":amin,"age_max":amax,"age_mid":amid,"event_type":e["event_type"],"confidence":num(e.get("confidence")) or 0}
        events[e["person_id"]].append(x);types.add(e["event_type"])
    types=sorted(types)

    sample=next(iter(people.values())) if people else {}
    bazi_fields=[k for k in sample if k.startswith("bazi__")]
    base=["person_id","adb_id","rodden_rating","gender","birth_country","calendar_kind","cutoff_age",
          "past_event_total","next_observed_event_type","next_observed_event_age","next_observed_event_delay",
          "next_observed_event_confidence"]
    fields=base+[f"past_count__{t}" for t in types]+bazi_fields
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=with_events=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,p in people.items():
            pe=sorted(events.get(pid,[]),key=lambda x:(x["age_mid"],x["age_min"]))
            if pe:with_events+=1
            # Only create rows when there is at least one observed future event after cutoff.
            # This avoids treating sparse Wikidata biographies as confirmed event-free lives.
            for cutoff in CUTS:
                past=[e for e in pe if e["age_max"]<=cutoff]
                future=[e for e in pe if e["age_min"]>cutoff]
                if not future:continue
                nxt=future[0];counts=Counter(e["event_type"] for e in past)
                row={
                  "person_id":pid,"adb_id":p.get("adb_id"),"rodden_rating":p.get("rodden_rating"),
                  "gender":p.get("gender"),"birth_country":p.get("birth_country"),
                  "calendar_kind":p.get("calendar_kind"),"cutoff_age":cutoff,
                  "past_event_total":len(past),"next_observed_event_type":nxt["event_type"],
                  "next_observed_event_age":round(nxt["age_mid"],3),
                  "next_observed_event_delay":round(nxt["age_mid"]-cutoff,3),
                  "next_observed_event_confidence":nxt["confidence"]
                }
                for t in types:row[f"past_count__{t}"]=counts[t]
                for k in bazi_fields:row[k]=p.get(k,"")
                wr.writerow(row);rows+=1
    report={
      "linked_people":len(people),"people_with_any_dated_event":with_events,"person_age_rows":rows,
      "cutoffs":list(CUTS),"event_types":types,
      "label_semantics":"next observed dated event; no-event rows intentionally excluded until censoring is modeled"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
