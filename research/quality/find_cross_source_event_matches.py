"""Find conservative cross-source event-match candidates without auto-merging them.

A candidate requires:
- same person
- different source systems
- same canonical event family
- overlapping date intervals OR <= configured year gap

Exact matching subject IDs raise confidence. Subject-less same-year matches remain review candidates,
not automatic corroboration.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from datetime import date
from pathlib import Path

def open_csv(path):
    return gzip.open(path,"rt",encoding="utf-8",newline="") if str(path).endswith(".gz") else open(path,"r",encoding="utf-8",newline="")

def src(row):
    raw=(row.get("source_families") or "").strip()
    if raw:return raw.split("|")[0]
    s=(row.get("source_id") or "").lower()
    if s.startswith("wikipedia"):return "wikipedia"
    return s or "unknown"

def fam(row):
    return (row.get("event_family") or row.get("event_type") or "").strip()

def dt(raw):
    try:return date.fromisoformat((raw or "")[:10])
    except:return None

def interval(row):
    lo=dt(row.get("event_date_min"));hi=dt(row.get("event_date_max"))
    return lo,hi

def overlaps(a,b):
    alo,ahi=interval(a);blo,bhi=interval(b)
    return bool(alo and ahi and blo and bhi and max(alo,blo)<=min(ahi,bhi))

def year_gap(a,b):
    alo,_=interval(a);blo,_=interval(b)
    if not alo or not blo:return None
    return abs(alo.year-blo.year)

def subject(row):
    return (row.get("subject_id") or "").strip().lower()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output");ap.add_argument("inputs",nargs="+")
    ap.add_argument("--max-year-gap",type=int,default=1)
    args=ap.parse_args()
    by=defaultdict(list)
    for raw in args.inputs:
        with open_csv(raw) as f:
            for r in csv.DictReader(f):
                pid=(r.get("person_id") or "").strip()
                if pid:by[pid].append(r)
    fields=[
      "person_id","event_family","left_event_id","right_event_id","left_source","right_source",
      "left_date_min","left_date_max","right_date_min","right_date_max",
      "date_overlap","year_gap","subject_match","left_subject_id","right_subject_id",
      "match_strength","requires_review"
    ]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    n=strong=0;people=set()
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,evs in by.items():
            for i,a in enumerate(evs):
                sa=src(a);fa=fam(a)
                if not fa:continue
                for b in evs[i+1:]:
                    sb=src(b)
                    if sa==sb:continue
                    if fam(b)!=fa:continue
                    ov=overlaps(a,b);gap=year_gap(a,b)
                    if not ov and (gap is None or gap>args.max_year_gap):continue
                    asub=subject(a);bsub=subject(b);sm=bool(asub and bsub and asub==bsub)
                    strength="strong" if (ov and sm) else ("medium" if ov else "weak")
                    strong+=int(strength=="strong");n+=1;people.add(pid)
                    wr.writerow({
                      "person_id":pid,"event_family":fa,
                      "left_event_id":a.get("event_id") or a.get("canonical_event_id") or "",
                      "right_event_id":b.get("event_id") or b.get("canonical_event_id") or "",
                      "left_source":sa,"right_source":sb,
                      "left_date_min":a.get("event_date_min") or "","left_date_max":a.get("event_date_max") or "",
                      "right_date_min":b.get("event_date_min") or "","right_date_max":b.get("event_date_max") or "",
                      "date_overlap":str(ov).lower(),"year_gap":"" if gap is None else gap,
                      "subject_match":str(sm).lower(),"left_subject_id":asub,"right_subject_id":bsub,
                      "match_strength":strength,"requires_review":"true"
                    })
    report={
      "match_candidates":n,"people_with_match_candidates":len(people),"strong_subject_and_date_matches":strong,
      "policy":"candidate generation only; no automatic evidence-independence or canonical merge claim"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
