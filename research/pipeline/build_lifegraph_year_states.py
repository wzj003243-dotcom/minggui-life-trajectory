"""Build domain-agnostic annual LifeGraph state vectors from normalized life events.

The state uses only events observable by the end of each year and is therefore suitable for
cutoff-safe models. Specialized academic/music state tables can be joined on person_id/year.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path

DOMAINS=("education","career","migration","creation","recognition","organization","relationship","family","setback","finance","legal","performance")

def entropy(c):
    n=sum(c.values())
    return 0.0 if not n else -sum((v/n)*math.log(v/n) for v in c.values() if v)

def source_family(s):
    s=(s or "").lower()
    if s.startswith("wikipedia"):return "wikipedia"
    if s=="wikidata":return "wikidata"
    if s=="openalex":return "openalex"
    if s=="musicbrainz":return "musicbrainz"
    return s or "unknown"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("output")
    ap.add_argument("--additional-events",nargs="*",default=[])
    args=ap.parse_args()
    by=defaultdict(list)
    for raw in [args.events]+list(args.additional_events):
        with gzip.open(raw,"rt",encoding="utf-8",newline="") as f:
            for r in csv.DictReader(f):
                try:y=int((r.get("observable_from") or r.get("event_date_max") or "")[:4])
                except:continue
                by[r["person_id"]].append((y,r))
    fields=["person_id","year","events_this_year","cumulative_events","domains_this_year",
            "cumulative_domain_breadth","cumulative_domain_entropy","source_families_this_year",
            "cumulative_source_family_breadth","rolling_3y_events",
            "years_since_last_event","event_type_switches_cumulative"] + \
           [f"year_count__{d}" for d in DOMAINS] + [f"cum_count__{d}" for d in DOMAINS]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=0;people=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,items in by.items():
            people+=1;yearly=defaultdict(list)
            for y,r in items:yearly[y].append(r)
            ys=sorted(yearly);cum=Counter();cum_sources=Counter();cum_events=0;hist={};last_event_year=None;last_type=None;switches=0
            for y in range(min(ys),max(ys)+1):
                evs=sorted(yearly.get(y,[]),key=lambda r:(r.get("event_date_min",""),r.get("event_id","")))
                yc=Counter(r.get("domain") or "other" for r in evs)
                sc=Counter(source_family(r.get("source_id")) for r in evs)
                for r in evs:
                    et=r.get("event_type") or ""
                    if last_type is not None and et and et!=last_type:switches+=1
                    if et:last_type=et
                    last_event_year=y
                cum.update(yc);cum_sources.update(sc);cum_events+=len(evs);hist[y]=len(evs)
                row={
                  "person_id":pid,"year":y,"events_this_year":len(evs),"cumulative_events":cum_events,
                  "domains_this_year":len([k for k,v in yc.items() if v]),
                  "cumulative_domain_breadth":len([k for k,v in cum.items() if v]),
                  "cumulative_domain_entropy":round(entropy(cum),6),
                  "source_families_this_year":len([k for k,v in sc.items() if v]),
                  "cumulative_source_family_breadth":len([k for k,v in cum_sources.items() if v]),
                  "rolling_3y_events":sum(hist.get(k,0) for k in (y-2,y-1,y)),
                  "years_since_last_event":"" if last_event_year is None else y-last_event_year,
                  "event_type_switches_cumulative":switches
                }
                for d in DOMAINS:
                    row[f"year_count__{d}"]=yc[d];row[f"cum_count__{d}"]=cum[d]
                wr.writerow(row);rows+=1
    report={"people":people,"year_state_rows":rows,"domains":list(DOMAINS),
            "input_event_files":1+len(args.additional_events),
            "cutoff_rule":"all features use events observable by end of state year"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
