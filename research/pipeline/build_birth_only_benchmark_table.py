"""Assemble a birth-only historical benchmark table.

Targets may be later-life outcomes; predictors are restricted to birth-time-observable reality
controls and objective BaZi features. This is an intentionally simple first falsification test,
not the final lifetime trajectory model.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from pathlib import Path

VALID_OCC={"Culture","Leadership","Discovery/Science","Sports/Games","Other"}

def read(path,key):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            k=(r.get(key) or "").strip()
            if k:out[k]=r
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bhht_sample")
    ap.add_argument("reality_controls")
    ap.add_argument("bazi_features")
    ap.add_argument("output")
    args=ap.parse_args()

    bhht=read(Path(args.bhht_sample),"wikidata_code")
    ctrl=read(Path(args.reality_controls),"person_id")
    bazi=read(Path(args.bazi_features),"person_id")
    bazi_fields=[]
    if bazi:
        bazi_fields=[k for k in next(iter(bazi.values())).keys() if k!="person_id"]

    base=[
      "person_id","target_level1_occupation","birth_year","birth_month","birth_day","day_of_year",
      "day_of_year_sin","day_of_year_cos","month_sin","month_cos","gender","birth_latitude",
      "birth_longitude","birth_region","birth_subregion","calendar_model","sampling_weight",
      "split_birth_era","split_region"
    ]
    fields=base+[f"bazi__{k}" for k in bazi_fields]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=0;target_counts={};missing_bazi=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,c in ctrl.items():
            m=bhht.get(pid);b=bazi.get(pid)
            if not m:continue
            target=m.get("level1_main_occ","")
            if target not in VALID_OCC:continue
            if not b:
                missing_bazi+=1;continue
            by=int(c["birth_year"])
            era=(by//25)*25
            row={
              "person_id":pid,"target_level1_occupation":target,
              "birth_year":c.get("birth_year"),"birth_month":c.get("birth_month"),"birth_day":c.get("birth_day"),
              "day_of_year":c.get("day_of_year"),"day_of_year_sin":c.get("day_of_year_sin"),
              "day_of_year_cos":c.get("day_of_year_cos"),"month_sin":c.get("month_sin"),"month_cos":c.get("month_cos"),
              "gender":c.get("gender"),"birth_latitude":c.get("birth_latitude"),"birth_longitude":c.get("birth_longitude"),
              "birth_region":c.get("birth_region"),"birth_subregion":c.get("birth_subregion"),
              "calendar_model":c.get("calendar_model"),"sampling_weight":c.get("sampling_weight"),
              "split_birth_era":f"{era}-{era+24}","split_region":c.get("birth_region")
            }
            for k in bazi_fields:row[f"bazi__{k}"]=b.get(k,"")
            wr.writerow(row);rows+=1;target_counts[target]=target_counts.get(target,0)+1

    report={
      "rows":rows,"target_counts":target_counts,"missing_bazi_features":missing_bazi,
      "predictor_policy":"birth-observable controls + objective BaZi only",
      "forbidden_predictors":["final occupation subtypes","Wikipedia edition count","visibility rank","awards","later-life events"],
      "intended_comparisons":["reality-only","BaZi-only","mixed","shuffled-birthday placebo"]
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
