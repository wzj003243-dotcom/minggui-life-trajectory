"""Normalize external dated event streams (OpenAlex / MusicBrainz) into MingGui LifeGraph.

Requires a canonical birth table keyed by Wikidata QID. Partial dates are represented as intervals,
never promoted to fake day precision.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from calendar import monthrange
from datetime import date
from pathlib import Path

def parse_births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or r.get("person_id") or "").strip()
            d=r.get("birth_date") or r.get("birth_date_normalized") or ""
            try:
                if q and d:out[q]=date.fromisoformat(d[:10])
            except:pass
    return out

def interval(raw):
    raw=(raw or "").strip()
    try:
        if len(raw)>=10:
            d=date.fromisoformat(raw[:10]);return d,d,"day"
        if len(raw)==7:
            y,m=map(int,raw.split("-"));return date(y,m,1),date(y,m,monthrange(y,m)[1]),"month"
        if len(raw)==4:
            y=int(raw);return date(y,1,1),date(y,12,31),"year"
    except:pass
    return None

def age(b,d):return round((d-b).days/365.2425,4)

def source_conf(source):
    return {"openalex":0.92,"musicbrainz":0.90}.get(source,0.75)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("births");ap.add_argument("output");ap.add_argument("inputs",nargs="+")
    args=ap.parse_args()
    births=parse_births(Path(args.births))
    fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max",
            "temporal_precision","age_min","age_max","age_mid","subject_id","source_id",
            "source_url","extraction_method","confidence","observable_from","attributes_json"]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    n=0;people=set();missing_birth=bad_date=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for rawpath in args.inputs:
            with gzip.open(rawpath,"rt",encoding="utf-8",newline="") as f:
                for r in csv.DictReader(f):
                    pid=(r.get("person_id") or "").strip();b=births.get(pid)
                    if not b:missing_birth+=1;continue
                    x=interval(r.get("event_date"))
                    if not x:bad_date+=1;continue
                    lo,hi,prec=x;amid=round((age(b,lo)+age(b,hi))/2,4)
                    et=r.get("event_type") or "other.external"
                    source=r.get("source_id") or ""
                    subject=r.get("openalex_work_id") or r.get("musicbrainz_id") or ""
                    attrs={k:v for k,v in r.items() if k not in {
                      "event_id","person_id","event_type","event_date","source_id","source_url"
                    } and v not in ("",None)}
                    wr.writerow({
                      "event_id":r.get("event_id") or f"{pid}:{source}:{n}",
                      "person_id":pid,"domain":et.split(".",1)[0],"event_type":et,
                      "event_date_min":lo.isoformat(),"event_date_max":hi.isoformat(),
                      "temporal_precision":prec,"age_min":age(b,lo),"age_max":age(b,hi),
                      "age_mid":amid,"subject_id":subject,"source_id":source,
                      "source_url":r.get("source_url") or "","extraction_method":"structured-external",
                      "confidence":source_conf(source),"observable_from":hi.isoformat(),
                      "attributes_json":json.dumps(attrs,ensure_ascii=False,separators=(",",":"))
                    });n+=1;people.add(pid)
    report={"lifegraph_event_rows":n,"people":len(people),"missing_birth_rows":missing_birth,"invalid_date_rows":bad_date}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
