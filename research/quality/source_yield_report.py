"""Report per-source LifeGraph yield and overlap.

Example:
  python source_yield_report.py out.json \
    --source wikidata=life_events_wikidata.csv.gz \
    --source openalex=life_events_openalex.csv.gz

The report is descriptive only; event volume is not treated as event importance.
"""
from __future__ import annotations
import argparse,csv,gzip,json,statistics
from collections import Counter,defaultdict
from pathlib import Path

def open_csv(path):
    return gzip.open(path,"rt",encoding="utf-8",newline="") if str(path).endswith(".gz") else open(path,"r",encoding="utf-8",newline="")

def parse_source(spec):
    if "=" not in spec:raise ValueError("source must be label=path")
    label,path=spec.split("=",1)
    return label.strip(),Path(path.strip())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--source",action="append",default=[],required=True)
    args=ap.parse_args()

    sources={}
    for spec in args.source:
        label,path=parse_source(spec)
        people=defaultdict(int);domains=Counter();types=Counter();rows=0
        with open_csv(path) as f:
            for r in csv.DictReader(f):
                pid=(r.get("person_id") or "").strip()
                if not pid:continue
                dom=(r.get("domain") or (r.get("event_type") or "").split(".",1)[0] or "unknown").strip()
                et=(r.get("event_family") or r.get("event_type") or "unknown").strip()
                people[pid]+=1;domains[dom]+=1;types[et]+=1;rows+=1
        counts=sorted(people.values())
        sources[label]={
          "path":str(path),"event_rows":rows,"people_set":set(people),
          "people_count":len(people),
          "events_per_hit_person_median":statistics.median(counts) if counts else 0,
          "events_per_hit_person_p90":counts[min(len(counts)-1,round((len(counts)-1)*.9))] if counts else 0,
          "domain_counts":dict(domains),
          "top_event_types":types.most_common(20)
        }

    labels=list(sources)
    overlap={}
    for a in labels:
        overlap[a]={}
        for b in labels:
            pa=sources[a]["people_set"];pb=sources[b]["people_set"]
            overlap[a][b]=len(pa & pb)

    summaries={}
    all_sets={k:v["people_set"] for k,v in sources.items()}
    union_all=set().union(*all_sets.values()) if all_sets else set()
    for label,v in sources.items():
        others=set().union(*(all_sets[k] for k in labels if k!=label)) if len(labels)>1 else set()
        summaries[label]={
          "event_rows":v["event_rows"],"people_count":v["people_count"],
          "people_unique_to_source":len(v["people_set"]-others),
          "events_per_hit_person_median":v["events_per_hit_person_median"],
          "events_per_hit_person_p90":v["events_per_hit_person_p90"],
          "domain_counts":v["domain_counts"],"top_event_types":v["top_event_types"]
        }

    report={"sources":summaries,"person_overlap_matrix":overlap,"union_people":len(union_all)}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
