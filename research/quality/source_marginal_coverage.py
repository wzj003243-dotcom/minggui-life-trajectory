"""Measure marginal LifeGraph coverage lift from each source/addon.

Example:
  python source_marginal_coverage.py out.json --cohort core.csv.gz \
    --base structured=structured.csv.gz \
    --addon family=family.csv.gz \
    --addon openalex=openalex.csv.gz

Each addon is evaluated both:
1) base + that addon (isolated marginal lift)
2) cumulative in the order supplied
The same thickness semantics as lifegraph_coverage_report are used, including high-frequency
person-year-family collapse for papers/music/performance.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from pathlib import Path

STAGES=[(0,18,"0-17"),(18,25,"18-24"),(25,35,"25-34"),(35,50,"35-49"),(50,65,"50-64"),(65,200,"65+")]
HF={"creation.scholar_output","creation.music_output","performance.event"}

def open_csv(p):
    return gzip.open(p,"rt",encoding="utf-8",newline="") if str(p).endswith(".gz") else open(p,"r",encoding="utf-8",newline="")

def num(x):
    try:return float(x)
    except:return None

def stage(age):
    if age is None:return None
    for lo,hi,n in STAGES:
        if lo<=age<hi:return n
    return None

def source_family(s):
    s=(s or "").lower()
    if s.startswith("wikipedia"):return "wikipedia"
    if s=="wikidata":return "wikidata"
    if s=="openalex":return "openalex"
    if s=="musicbrainz":return "musicbrainz"
    return s or "unknown"

def family(row):
    x=(row.get("event_family") or "").strip()
    if x:return x
    e=(row.get("event_type") or "").lower()
    if "creation.scholar_work" in e:return "creation.scholar_output"
    if "creation.music_release_group" in e:return "creation.music_output"
    if "performance.music_event" in e:return "performance.event"
    return e or ((row.get("domain") or "unknown")+".other")

def year(row):
    raw=(row.get("event_date_min") or row.get("observable_from") or "")
    try:return int(raw[:4])
    except:return None

def read_ids(cohort):
    ids=[]
    with open_csv(cohort) as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or r.get("person_id") or r.get("wikidata_code") or "").strip()
            if q:ids.append(q)
    return list(dict.fromkeys(ids))

def read_events(path):
    out=[]
    with open_csv(path) as f:
        for r in csv.DictReader(f):
            if (r.get("person_id") or "").strip():out.append(r)
    return out

def score(ids,event_lists):
    p={q:{"raw":0,"domains":set(),"stages":set(),"sources":set(),"effective":set()} for q in ids}
    idx=0
    for events in event_lists:
        for r in events:
            q=(r.get("person_id") or "").strip()
            if q not in p:continue
            x=p[q];x["raw"]+=1
            dom=(r.get("domain") or (r.get("event_type") or "").split(".",1)[0] or "unknown").strip()
            x["domains"].add(dom)
            st=stage(num(r.get("age_mid") or r.get("age_years")))
            if st:x["stages"].add(st)
            rawsrc=(r.get("source_families") or "").strip()
            srcs=[s for s in rawsrc.split("|") if s] if rawsrc else [source_family(r.get("source_id"))]
            x["sources"].update(srcs)
            fam=family(r);yr=year(r)
            if fam in HF and yr is not None:
                x["effective"].add(("yf",yr,fam))
            else:
                eid=r.get("canonical_event_id") or r.get("event_id") or f"row:{idx}"
                x["effective"].add(("event",str(eid)))
            idx+=1
    tiers={};counts={"thin":0,"bronze":0,"silver":0,"gold":0}
    for q,x in p.items():
        e=len(x["effective"]);d=len(x["domains"]);s=len(x["stages"]);src=len(x["sources"])
        gold=e>=25 and d>=5 and s>=4 and src>=2
        silver=e>=15 and d>=4 and s>=3 and src>=2
        bronze=e>=8 and d>=3 and s>=2 and src>=1
        tier="gold" if gold else ("silver" if silver else ("bronze" if bronze else "thin"))
        tiers[q]=tier;counts[tier]+=1
    return tiers,counts

def transitions(before,after):
    order={"thin":0,"bronze":1,"silver":2,"gold":3}
    c=defaultdict(int)
    improved=0
    for q,b in before.items():
        a=after[q]
        if order[a]>order[b]:
            c[f"{b}->{a}"]+=1;improved+=1
    return {"people_improved":improved,"transitions":dict(c)}

def parse_specs(vals):
    out=[]
    for v in vals:
        name,path=v.split("=",1);out.append((name,path))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("--cohort",required=True)
    ap.add_argument("--base",action="append",default=[],help="name=path; may repeat")
    ap.add_argument("--addon",action="append",default=[],help="name=path; order defines cumulative sequence")
    args=ap.parse_args()
    ids=read_ids(args.cohort)
    bases=[(n,read_events(p)) for n,p in parse_specs(args.base)]
    addons=[(n,read_events(p)) for n,p in parse_specs(args.addon)]
    base_events=[e for _,e in bases]
    base_tiers,base_counts=score(ids,base_events)
    isolated={}
    for name,ev in addons:
        tiers,counts=score(ids,base_events+[ev])
        isolated[name]={"tier_counts":counts,"lift":transitions(base_tiers,tiers),"event_rows":len(ev)}
    cumulative={}
    cur=list(base_events);prev_tiers=base_tiers
    for name,ev in addons:
        cur.append(ev);tiers,counts=score(ids,cur)
        cumulative[name]={"tier_counts":counts,"step_lift":transitions(prev_tiers,tiers),"event_rows_added":len(ev)}
        prev_tiers=tiers
    report={
      "people":len(ids),
      "base_sources":[n for n,_ in bases],
      "base_tier_counts":base_counts,
      "isolated_marginal":isolated,
      "cumulative_order":[n for n,_ in addons],
      "cumulative":cumulative,
      "final_tier_counts":cumulative[list(cumulative)[-1]]["tier_counts"] if cumulative else base_counts
    }
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
