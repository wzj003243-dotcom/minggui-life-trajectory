"""Convert dated Wikidata claim rows into cutoff-ready atomic life events."""
from __future__ import annotations
import argparse,csv,gzip,json
from datetime import date
from pathlib import Path

def parse_wd_time_obj(obj):
    raw=(obj or {}).get("time")
    if not raw:return None,None
    p=int(obj.get("precision") or 0)
    s=raw.lstrip("+")
    y=int(s[0:4]);m=int(s[5:7] or 1);d=int(s[8:10] or 1)
    if p<=9:return f"{y:04d}","year"
    if p==10:return f"{y:04d}-{m:02d}","month"
    return f"{y:04d}-{m:02d}-{d:02d}","day"

def first_time(raw):
    try:xs=json.loads(raw or "[]")
    except:xs=[]
    return parse_wd_time_obj(xs[0]) if xs else (None,None)

def read_births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("birth_date") and r.get("canonical_status") in ("canonical_unique","canonical_preferred"):
                out[r["wikidata_id"]]=r["birth_date"]
    return out

def age_years(birth, event_date):
    try:
        by,bm,bd=map(int,birth.split("-"))
        parts=list(map(int,event_date.split("-")))
        ey=parts[0];em=parts[1] if len(parts)>1 else 7;ed=parts[2] if len(parts)>2 else 1
        return round((date(ey,em,ed)-date(by,bm,bd)).days/365.2425,3)
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("claims");ap.add_argument("canonical_births");ap.add_argument("output")
    args=ap.parse_args()
    births=read_births(Path(args.canonical_births))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["event_id","person_id","domain","event_type","start_date","end_date","point_date",
            "temporal_precision","age_start","age_end","age_point","subject_id","source_id",
            "extraction_method","confidence","observable_from","statement_rank","reference_count"]
    n=people=0;seen=set()
    with gzip.open(args.claims,"rt",encoding="utf-8",newline="") as f, gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f);wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for row in r:
            pid=row["person_id"]
            birth=births.get(pid)
            if not birth:continue
            start,sp=first_time(row.get("start_json"));end,ep=first_time(row.get("end_json"));point,pp=first_time(row.get("point_json"))
            vals=[(point,pp),(start,sp),(end,ep)]
            chosen=next(((d,p) for d,p in vals if d), (None,None))
            event_date,prec=chosen
            if not event_date:continue
            refs=int(row.get("reference_count") or 0)
            conf=min(.96,.62+.06*min(refs,5)+(.08 if row.get("rank")=="preferred" else 0))
            wr.writerow({
              "event_id":row.get("statement_id") or f"{pid}:{n}","person_id":pid,
              "domain":row["event_type"].split(".",1)[0],"event_type":row["event_type"],
              "start_date":start or "","end_date":end or "","point_date":point or "",
              "temporal_precision":prec or "unknown",
              "age_start":age_years(birth,start) if start else "",
              "age_end":age_years(birth,end) if end else "",
              "age_point":age_years(birth,point) if point else "",
              "subject_id":row.get("value_qid") or "","source_id":"wikidata",
              "extraction_method":"structured","confidence":conf,
              "observable_from":event_date,"statement_rank":row.get("rank") or "",
              "reference_count":refs
            })
            n+=1;seen.add(pid)
    report={"life_event_rows":n,"people_with_events":len(seen),"birth_people_available":len(births)}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
