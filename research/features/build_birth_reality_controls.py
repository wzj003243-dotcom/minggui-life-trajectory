"""Build leakage-safe birth-only reality/calendar controls for the exact-date cohort.

These features are deliberately non-metaphysical. They are the benchmark BaZi must beat.
Final occupation, award count, Wikipedia-edition count and later-life notability are excluded
because they would leak the outcome being predicted.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from datetime import date
from pathlib import Path

PRIMARY={"canonical_unique","canonical_preferred"}

def read_sample(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_code") or r.get("wikidata_id") or "").strip()
            if q:out[q]=r
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("canonical_births");ap.add_argument("bhht_sample");ap.add_argument("output")
    args=ap.parse_args()
    meta=read_sample(Path(args.bhht_sample))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=[
      "person_id","birth_date","birth_year","birth_month","birth_day","day_of_year",
      "day_of_year_sin","day_of_year_cos","month_sin","month_cos","calendar_model",
      "gender","birth_latitude","birth_longitude","birth_region","birth_subregion",
      "sampling_weight"
    ]
    n=missing_meta=0
    with gzip.open(args.canonical_births,"rt",encoding="utf-8",newline="") as f,gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f);wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for b in r:
            if b.get("canonical_status") not in PRIMARY or not b.get("birth_date"):continue
            try:d=date.fromisoformat(b["birth_date"][:10])
            except:continue
            q=b["wikidata_id"];m=meta.get(q,{})
            if not m:missing_meta+=1
            doy=d.timetuple().tm_yday
            wr.writerow({
              "person_id":q,"birth_date":d.isoformat(),"birth_year":d.year,"birth_month":d.month,"birth_day":d.day,
              "day_of_year":doy,
              "day_of_year_sin":math.sin(2*math.pi*doy/365.2425),
              "day_of_year_cos":math.cos(2*math.pi*doy/365.2425),
              "month_sin":math.sin(2*math.pi*d.month/12),
              "month_cos":math.cos(2*math.pi*d.month/12),
              "calendar_model":b.get("calendar_model",""),
              "gender":m.get("gender",""),"birth_latitude":m.get("bpla1",""),
              "birth_longitude":m.get("bplo1",""),"birth_region":m.get("un_region",""),
              "birth_subregion":m.get("un_subregion",""),"sampling_weight":m.get("sampling_weight","")
            });n+=1
    report={
      "rows":n,"missing_bhht_metadata":missing_meta,
      "feature_policy":"birth-only non-metaphysical controls; excludes final occupation/notability/later-life features",
      "purpose":"same-person baseline for testing incremental BaZi signal"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
