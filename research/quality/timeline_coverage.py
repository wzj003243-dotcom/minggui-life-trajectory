"""Audit per-person life-event coverage and cutoff usability.

Missing biography events are not negatives. This report quantifies how much of each person's
timeline is actually observed and identifies cutoffs with evidence on both sides.
"""
from __future__ import annotations
import argparse,csv,gzip,json,statistics
from collections import Counter,defaultdict
from pathlib import Path

CUTS=(18,25,30,40)

def fnum(x):
    try:return float(x)
    except:return None

def q(values,q):
    if not values:return None
    s=sorted(values)
    pos=(len(s)-1)*q
    lo=int(pos);hi=min(lo+1,len(s)-1);f=pos-lo
    return s[lo]*(1-f)+s[hi]*f

def main():
    ap=argparse.ArgumentParser();ap.add_argument("events");ap.add_argument("people_output");args=ap.parse_args()
    by=defaultdict(list);types=Counter();domains=Counter();rows=referenced=0
    with gzip.open(args.events,"rt",encoding="utf-8",newline="") as f:
        for e in csv.DictReader(f):
            amin=fnum(e.get("age_min"));amax=fnum(e.get("age_max"));conf=fnum(e.get("confidence"))
            if amin is None or amax is None:continue
            refs=int(float(e.get("reference_count") or 0))
            x={"age_min":amin,"age_max":amax,"event_type":e.get("event_type",""),
               "domain":e.get("domain",""),"confidence":conf or 0,"refs":refs}
            by[e["person_id"]].append(x);rows+=1;referenced+=refs>0
            types[x["event_type"]]+=1;domains[x["domain"]]+=1

    fields=["person_id","event_count","domain_count","first_event_age_min","last_event_age_max",
            "referenced_event_fraction","mean_confidence"]
    for cut in CUTS:
        fields += [f"past_events_at_{cut}",f"future_events_after_{cut}",
                   f"eligible_1x1_at_{cut}",f"eligible_2x2_at_{cut}",f"eligible_3x3_at_{cut}"]

    out=Path(args.people_output);out.parent.mkdir(parents=True,exist_ok=True)
    counts=[];spans=[];cutstats={c:Counter() for c in CUTS}
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,ev in sorted(by.items()):
            counts.append(len(ev))
            lo=min(e["age_min"] for e in ev);hi=max(e["age_max"] for e in ev);spans.append(hi-lo)
            row={
              "person_id":pid,"event_count":len(ev),"domain_count":len({e["domain"] for e in ev}),
              "first_event_age_min":round(lo,3),"last_event_age_max":round(hi,3),
              "referenced_event_fraction":round(sum(e["refs"]>0 for e in ev)/len(ev),4),
              "mean_confidence":round(sum(e["confidence"] for e in ev)/len(ev),4)
            }
            for cut in CUTS:
                past=sum(e["age_max"]<=cut for e in ev);future=sum(e["age_min"]>cut for e in ev)
                row[f"past_events_at_{cut}"]=past;row[f"future_events_after_{cut}"]=future
                for k in (1,2,3):
                    ok=past>=k and future>=k
                    row[f"eligible_{k}x{k}_at_{cut}"]=ok
                    cutstats[cut][f"eligible_{k}x{k}"]+=ok
            wr.writerow(row)

    report={
      "event_rows":rows,"people_with_events":len(by),
      "referenced_event_fraction":referenced/rows if rows else 0,
      "event_count_quantiles":{"p25":q(counts,.25),"p50":q(counts,.5),"p75":q(counts,.75),"p90":q(counts,.9)},
      "timeline_span_years_quantiles":{"p25":q(spans,.25),"p50":q(spans,.5),"p75":q(spans,.75)},
      "people_with_at_least":{"2_events":sum(x>=2 for x in counts),"5_events":sum(x>=5 for x in counts),"10_events":sum(x>=10 for x in counts)},
      "cutoff_eligibility":{str(c):dict(v) for c,v in cutstats.items()},
      "domain_counts":dict(domains.most_common()),"event_type_counts":dict(types.most_common()),
      "rule":"A missing event is never converted to a negative outcome solely from absence in Wikidata."
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
