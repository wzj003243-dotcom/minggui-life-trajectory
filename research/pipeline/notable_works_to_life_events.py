"""Normalize dated notable works into the common life-event schema."""
from __future__ import annotations
import argparse,csv,gzip,json,re
from calendar import monthrange
from datetime import date
from pathlib import Path

GREGORIAN="Q1985727"; JULIAN="Q1985786"

def julian_to_gregorian(y,m,d):
    a=(14-m)//12;yy=y+4800-a;mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044;b=(4*a+3)//146097;c=a-(146097*b)//4
    dd=(4*c+3)//1461;e=c-(1461*dd)//4;mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1;month=mm2+3-12*(mm2//10);year=100*b+dd-4800+(mm2//10)
    return date(year,month,day)

def cal_kind(uri):
    tail=(uri or "").rsplit("/",1)[-1]
    return "julian" if tail==JULIAN else ("gregorian" if tail==GREGORIAN else "unknown")

def interval(o):
    raw=o.get("time") or "";p=int(o.get("precision") or 0);cal=cal_kind(o.get("calendar_model"))
    m=re.match(r"^\+?(-?\d+)-(\d+)-(\d+)",raw)
    if not m:return None
    y,mo,da=map(int,m.groups())
    if y<=0 or y>9999 or p<9:return None
    if p==9: sm,sd,em,ed,label=1,1,12,31,"year"
    elif p==10:
        sm=em=mo;sd=1;ed=(29 if cal=="julian" and mo==2 and y%4==0 else (28 if cal=="julian" and mo==2 else (30 if cal=="julian" and mo in {4,6,9,11} else (31 if cal=="julian" else monthrange(y,mo)[1]))));label="month"
    else: sm=em=mo;sd=ed=da;label="day"
    try:
        if cal=="julian":lo=julian_to_gregorian(y,sm,sd);hi=julian_to_gregorian(y,em,ed)
        else:lo=date(y,sm,sd);hi=date(y,em,ed)
    except Exception:return None
    return lo,hi,label,cal,raw

def births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("canonical_status") in ("canonical_unique","canonical_preferred") and r.get("birth_date"):
                try:out[r["wikidata_id"]]=date.fromisoformat(r["birth_date"][:10])
                except:pass
    return out

def age(b,d):return round((d-b).days/365.2425,4) if b and d else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("works");ap.add_argument("canonical_births");ap.add_argument("output");args=ap.parse_args()
    bmap=births(Path(args.canonical_births));out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max","temporal_precision","calendar_kind","source_time_raw","age_min","age_max","age_mid","subject_id","source_id","extraction_method","confidence","observable_from","statement_rank","reference_count","qualifier_kind"]
    rows=0;people=set()
    with gzip.open(args.works,"rt",encoding="utf-8",newline="") as f,gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f);wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for row in r:
            pid=row["person_id"];b=bmap.get(pid)
            if not b:continue
            try:vals=json.loads(row.get("publication_json") or "[]")
            except:vals=[]
            for j,o in enumerate(vals):
                x=interval(o)
                if not x:continue
                lo,hi,prec,cal,raw=x;amin=age(b,lo);amax=age(b,hi);amid=round((amin+amax)/2,4)
                refs=int(o.get("reference_count") or 0);conf=min(.96,.64+.06*min(refs,5)+(.08 if o.get("rank")=="preferred" else 0))
                wr.writerow({
                  "event_id":f"{pid}:P800:{row['work_qid']}:{j}","person_id":pid,"domain":"creation",
                  "event_type":"creation.notable_work","event_date_min":lo.isoformat(),"event_date_max":hi.isoformat(),
                  "temporal_precision":prec,"calendar_kind":cal,"source_time_raw":raw,
                  "age_min":amin,"age_max":amax,"age_mid":amid,"subject_id":row["work_qid"],
                  "source_id":"wikidata","extraction_method":"structured-two-hop","confidence":conf,
                  "observable_from":hi.isoformat(),"statement_rank":o.get("rank") or "",
                  "reference_count":refs,"qualifier_kind":"publication"
                });rows+=1;people.add(pid)
    report={"creation_event_rows":rows,"people_with_dated_notable_works":len(people)}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
