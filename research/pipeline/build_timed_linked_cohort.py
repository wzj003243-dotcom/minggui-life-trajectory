"""Join Astro timed births, objective BaZi features, and Wikidata identities.

Output is keyed by Wikidata QID but preserves ADB id/provenance. This is the canonical bridge
for timed-cohort modeling: ADB birth evidence -> normalized birth instant/date -> BaZi features
-> Wikidata life events.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from pathlib import Path

PRIMARY={"AA","A","B"}

def read(path,key):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            k=(r.get(key) or "").strip()
            if k:out[k]=r
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("astro_births")
    ap.add_argument("validated_links")
    ap.add_argument("bazi_features")
    ap.add_argument("output")
    args=ap.parse_args()

    births=read(Path(args.astro_births),"adb_id")
    links=read(Path(args.validated_links),"adb_id")
    features=read(Path(args.bazi_features),"person_id")
    feature_fields=[]
    if features:
        feature_fields=[x for x in next(iter(features.values())).keys() if x!="person_id"]

    base_fields=[
      "wikidata_id","adb_id","name","gender","rodden_rating",
      "birth_date_normalized","birth_date_source","birth_time_local",
      "birth_place","birth_country","birth_latitude","birth_longitude",
      "wikipedia_url","adb_url","source_calendar","calendar_kind",
      "calendar_conversion","feature_version","death_date_normalized","death_year"
    ]
    out_fields=base_fields+[f"bazi__{x}" for x in feature_fields if x not in {
      "source_birth_date","birth_date","birth_time_local","source_calendar","calendar_kind",
      "calendar_conversion","feature_version"
    }]

    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=0;seen_q=set();duplicate_q=0;by_rating={};by_calendar={}
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=out_fields);wr.writeheader()
        for adb_id,b in births.items():
            if b.get("rodden_rating") not in PRIMARY:continue
            f=features.get(adb_id);ln=links.get(adb_id)
            if not f or not ln or not ln.get("wikidata_id") or ln.get("identity_status")!="verified_day_match":continue
            q=ln["wikidata_id"]
            if q in seen_q:
                duplicate_q+=1
                # Preserve one QID -> one timed birth row in primary cohort.
                # Duplicates remain visible in report for manual review.
                continue
            seen_q.add(q)
            rr=b["rodden_rating"];by_rating[rr]=by_rating.get(rr,0)+1
            cal=f.get("calendar_kind","");by_calendar[cal]=by_calendar.get(cal,0)+1
            death_exact=[x for x in (ln.get("wikidata_death_exact_dates") or "").split("|") if x]
            death_years=[x for x in (ln.get("wikidata_death_years") or "").split("|") if x]
            death_date=death_exact[0] if len(set(death_exact))==1 else ""
            death_year=death_years[0] if len(set(death_years))==1 else ""
            row={
              "wikidata_id":q,"adb_id":adb_id,"name":b.get("name",""),"gender":b.get("gender",""),
              "rodden_rating":rr,"birth_date_normalized":f.get("birth_date",""),
              "birth_date_source":b.get("birth_date",""),"birth_time_local":b.get("birth_time_local",""),
              "birth_place":b.get("place",""),"birth_country":b.get("country",""),
              "birth_latitude":b.get("latitude",""),"birth_longitude":b.get("longitude",""),
              "wikipedia_url":b.get("wikipedia_url",""),"adb_url":b.get("adb_url",""),
              "source_calendar":f.get("source_calendar",""),"calendar_kind":cal,
              "calendar_conversion":f.get("calendar_conversion",""),"feature_version":f.get("feature_version",""),
              "death_date_normalized":death_date,"death_year":death_year
            }
            for k in feature_fields:
                if k in {"source_birth_date","birth_date","birth_time_local","source_calendar","calendar_kind","calendar_conversion","feature_version"}:continue
                row[f"bazi__{k}"]=f.get(k,"")
            wr.writerow(row);rows+=1

    report={
      "linked_primary_timed_people":rows,
      "unique_wikidata_ids":len(seen_q),
      "duplicate_verified_wikidata_ids_skipped":duplicate_q,
      "identity_gate":"verified_day_match",
      "rodden_counts":by_rating,
      "calendar_counts":by_calendar,
      "feature_version":"bazi-objective-v0.1"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
