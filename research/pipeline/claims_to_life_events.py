"""Convert dated Wikidata claim rows into leakage-safe, age-aware atomic life events.

Time precision is represented as an interval rather than fake point precision:
- precision 11: exact civil day
- precision 10: whole month
- precision 9: whole year
- precision <9: retained as coarse source time but excluded from cutoff ordering

Julian-calendar intervals are converted to the equivalent proleptic Gregorian physical-day
interval before ages are calculated. For cutoff safety, observable_from uses the *latest*
possible day in the event interval, so an imprecise year-level fact cannot leak into an
earlier point in that same year.
"""
from __future__ import annotations
import argparse,csv,gzip,json,re
from calendar import monthrange
from datetime import date
from pathlib import Path

GREGORIAN="Q1985727"
JULIAN="Q1985786"

def julian_to_gregorian(y:int,m:int,d:int):
    if y <= 0:
        return None
    a=(14-m)//12
    yy=y+4800-a
    mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044
    b=(4*a+3)//146097
    c=a-(146097*b)//4
    dd=(4*c+3)//1461
    e=c-(1461*dd)//4
    mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1
    month=mm2+3-12*(mm2//10)
    year=100*b+dd-4800+(mm2//10)
    return date(year,month,day)

def julian_month_days(y:int,m:int):
    if m==2:
        return 29 if y%4==0 else 28
    return 30 if m in {4,6,9,11} else 31

def calendar_kind(uri:str|None):
    tail=(uri or "").rsplit("/",1)[-1]
    if tail==JULIAN:return "julian"
    if tail==GREGORIAN:return "gregorian"
    return "unknown"

def raw_year(raw:str):
    m=re.match(r"^\+?(-?\d+)-",raw or "")
    return int(m.group(1)) if m else None

def time_interval(obj):
    """Return (lo_date, hi_date, precision_label, calendar_kind, source_raw)."""
    if not obj or not obj.get("time"):
        return None,None,"unknown","unknown",None
    raw=obj["time"]
    p=int(obj.get("precision") or 0)
    cal=calendar_kind(obj.get("calendar_model"))
    y=raw_year(raw)
    if y is None or y<=0 or y>9999:
        return None,None,"unsupported",cal,raw
    # Precision below year is too coarse for cutoff-safe event ordering.
    if p < 9:
        return None,None,"coarse",cal,raw
    try:
        m=int(raw.split("T",1)[0].split("-")[1])
        d=int(raw.split("T",1)[0].split("-")[2])
    except Exception:
        m=d=0

    if p==9:
        sm,sd,em=1,1,12
        ed=31
        label="year"
    elif p==10:
        if not 1<=m<=12:return None,None,"invalid",cal,raw
        sm=em=m;sd=1
        ed=julian_month_days(y,m) if cal=="julian" else monthrange(y,m)[1]
        label="month"
    else:
        if not (1<=m<=12 and d>=1):return None,None,"invalid",cal,raw
        sm=em=m;sd=ed=d
        label="day"

    try:
        if cal=="julian":
            lo=julian_to_gregorian(y,sm,sd)
            hi=julian_to_gregorian(y,em,ed)
        else:
            # Unknown calendar is not silently called Gregorian. Modern Wikidata event claims
            # overwhelmingly carry an explicit calendar model; unknown is flagged downstream.
            lo=date(y,sm,sd);hi=date(y,em,ed)
    except Exception:
        return None,None,"invalid",cal,raw
    return lo,hi,label,cal,raw

def first_time(raw):
    try:xs=json.loads(raw or "[]")
    except Exception:xs=[]
    return time_interval(xs[0]) if xs else (None,None,"unknown","unknown",None)

def read_births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("birth_date") and r.get("canonical_status") in ("canonical_unique","canonical_preferred"):
                try:out[r["wikidata_id"]]=date.fromisoformat(r["birth_date"][:10])
                except Exception:pass
    return out

def age(birth:date|None,d:date|None):
    if not birth or not d:return None
    return round((d-birth).days/365.2425,4)

def iso(d):return d.isoformat() if d else ""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("claims");ap.add_argument("canonical_births");ap.add_argument("output")
    args=ap.parse_args()
    births=read_births(Path(args.canonical_births))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=[
      "event_id","person_id","domain","event_type",
      "event_date_min","event_date_max","temporal_precision","calendar_kind","source_time_raw",
      "age_min","age_max","age_mid",
      "subject_id","source_id","extraction_method","confidence","observable_from",
      "statement_rank","reference_count","qualifier_kind"
    ]
    n=0;seen=set();coarse=0;unknown_cal=0;julian=0
    with gzip.open(args.claims,"rt",encoding="utf-8",newline="") as f, gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f);wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for row in r:
            pid=row["person_id"];birth=births.get(pid)
            if not birth:continue
            point=first_time(row.get("point_json"))
            start=first_time(row.get("start_json"))
            end=first_time(row.get("end_json"))
            refs=int(row.get("reference_count") or 0)
            conf=min(.96,.62+.06*min(refs,5)+(.08 if row.get("rank")=="preferred" else 0))

            # Preserve all dated temporal qualifiers. A relation carrying both start and end
            # becomes two atomic timeline nodes instead of silently dropping the end.
            candidates=[("point",point),("start",start),("end",end)]
            emitted_for_claim=0
            for kind,data in candidates:
                lo,hi,prec,cal,raw=data
                if not (lo or prec=="coarse"):
                    continue
                if prec=="coarse":
                    coarse+=1
                    continue
                if not lo or not hi:
                    continue
                if cal=="unknown":unknown_cal+=1
                if cal=="julian":julian+=1
                amin=age(birth,lo);amax=age(birth,hi)
                amid=round((amin+amax)/2,4) if amin is not None and amax is not None else None
                base_type=row["event_type"]
                event_type=base_type if kind=="point" else f"{base_type}.{kind}"
                statement=row.get("statement_id") or f"{pid}:{n}"
                wr.writerow({
                  "event_id":f"{statement}:{kind}","person_id":pid,
                  "domain":base_type.split(".",1)[0],"event_type":event_type,
                  "event_date_min":iso(lo),"event_date_max":iso(hi),
                  "temporal_precision":prec,"calendar_kind":cal,"source_time_raw":raw or "",
                  "age_min":amin if amin is not None else "","age_max":amax if amax is not None else "",
                  "age_mid":amid if amid is not None else "",
                  "subject_id":row.get("value_qid") or "","source_id":"wikidata",
                  "extraction_method":"structured","confidence":conf,
                  "observable_from":iso(hi),"statement_rank":row.get("rank") or "",
                  "reference_count":refs,"qualifier_kind":kind
                })
                n+=1;emitted_for_claim+=1;seen.add(pid)
    report={
      "life_event_rows":n,"people_with_events":len(seen),"birth_people_available":len(births),
      "coarse_claims_excluded_from_ordering":coarse,
      "unknown_calendar_event_rows":unknown_cal,"julian_event_rows_converted":julian,
      "cutoff_policy":"observable_from = latest possible date in source precision interval"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
