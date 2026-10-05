"""Measure LifeGraph thickness per person and cohort.

Default "model-ready thick" rule:
- >= 15 dated events
- >= 4 event domains
- >= 3 life stages containing at least one event
- >= 2 independent source families

The report never treats publication-level scholarly works as equivalent to major life events:
it reports both raw event counts and source/domain/stage coverage.
"""
from __future__ import annotations
import argparse,csv,gzip,json,statistics
from collections import Counter,defaultdict
from pathlib import Path

STAGES=[(0,18,"0-17"),(18,25,"18-24"),(25,35,"25-34"),(35,50,"35-49"),(50,65,"50-64"),(65,200,"65+")]

def num(x):
    try:return float(x)
    except:return None

def source_family(s):
    s=(s or "").lower()
    if s.startswith("wikipedia"):return "wikipedia"
    if s=="wikidata":return "wikidata"
    if s=="openalex":return "openalex"
    if s=="musicbrainz":return "musicbrainz"
    return s or "unknown"

def stage(age):
    if age is None:return None
    for lo,hi,name in STAGES:
        if lo<=age<hi:return name
    return None

def open_csv(path):
    return gzip.open(path,"rt",encoding="utf-8",newline="") if str(path).endswith(".gz") else open(path,"r",encoding="utf-8",newline="")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("inputs",nargs="+")
    ap.add_argument("--cohort",default="",help="optional CSV[.gz] cohort used as denominator, including zero-event people")
    ap.add_argument("--cohort-id-column",default="wikidata_id")
    ap.add_argument("--min-events",type=int,default=15)
    ap.add_argument("--min-domains",type=int,default=4)
    ap.add_argument("--min-stages",type=int,default=3)
    ap.add_argument("--min-sources",type=int,default=2)
    args=ap.parse_args()

    people=defaultdict(lambda:{"events":0,"domains":Counter(),"stages":Counter(),"sources":Counter(),"types":Counter()})
    if args.cohort:
        with open_csv(args.cohort) as cf:
            for row in csv.DictReader(cf):
                pid=(row.get(args.cohort_id_column) or row.get("person_id") or row.get("wikidata_code") or "").strip()
                if pid:
                    _=people[pid]
    total=0
    for raw in args.inputs:
        with open_csv(raw) as f:
            r=csv.DictReader(f)
            for x in r:
                pid=(x.get("person_id") or x.get("wikidata_id") or "").strip()
                if not pid:continue
                age=num(x.get("age_mid") or x.get("age_years"))
                dom=(x.get("domain") or (x.get("event_type") or "").split(".",1)[0] or "unknown").strip()
                src=source_family(x.get("source_id"))
                st=stage(age)
                p=people[pid];p["events"]+=1;p["domains"][dom]+=1;p["sources"][src]+=1
                p["types"][x.get("event_type") or "unknown"]+=1
                if st:p["stages"][st]+=1
                total+=1

    rows=[];ready=0
    for pid,p in people.items():
        ok=(p["events"]>=args.min_events and len(p["domains"])>=args.min_domains and
            len(p["stages"])>=args.min_stages and len(p["sources"])>=args.min_sources)
        ready+=int(ok)
        rows.append({
          "person_id":pid,"event_count":p["events"],"domain_count":len(p["domains"]),
          "stage_count":len(p["stages"]),"source_family_count":len(p["sources"]),
          "model_ready_thick":ok,"domains":dict(p["domains"]),"stages":dict(p["stages"]),
          "sources":dict(p["sources"])
        })
    counts=sorted(x["event_count"] for x in rows)
    def q(frac):
        if not counts:return 0
        return counts[min(len(counts)-1,round((len(counts)-1)*frac))]
    report={
      "people":len(rows),"event_rows":total,
      "denominator":"explicit cohort including zero-event people" if args.cohort else "people observed in event inputs",
      "event_count":{"median":statistics.median(counts) if counts else 0,"p25":q(.25),"p75":q(.75),"p90":q(.90)},
      "model_ready_thick_people":ready,
      "model_ready_thick_share":(ready/len(rows) if rows else 0),
      "thresholds":{"min_events":args.min_events,"min_domains":args.min_domains,"min_stages":args.min_stages,"min_sources":args.min_sources},
      "life_stages":[x[2] for x in STAGES]
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"summary":report,"people":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
