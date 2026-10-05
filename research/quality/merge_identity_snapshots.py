"""Merge multiple identity-validation snapshots into a persistent-consensus final table.

Principle:
- A prior verified_day_match is positive evidence and is retained.
- API/transient missingness must never erase a previous verification.
- Rows never successfully verified are re-queried by the lossless validator.
- Deterministic no-QID / no-primary-feature rows need no external retry.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from pathlib import Path

FIELDS=[
 "adb_id","rodden_rating","wikidata_id","wikipedia_url","astro_birth_date_normalized",
 "wikidata_day_dates","identity_status","matching_date","wikidata_birth_assertions_json",
 "wikidata_death_exact_dates","wikidata_death_years","wikidata_death_assertions_json"
]

def read_rows(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def by_adb(rows):
    return {r.get("adb_id",""):r for r in rows if r.get("adb_id")}

def write(path,rows,fields=FIELDS):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:r.get(k,"") for k in fields})

def prepare(args):
    old=by_adb(read_rows(args.old_validation))
    cur=by_adb(read_rows(args.current_validation))
    links=read_rows(args.current_links)
    verified={}
    for aid in sorted(set(old)|set(cur)):
        choices=[r for r in (cur.get(aid),old.get(aid)) if r and r.get("identity_status")=="verified_day_match"]
        if choices:
            # Prefer current if both verified; either is valid positive evidence.
            verified[aid]=choices[0]
    deterministic={}
    retry_aids=set()
    for l in links:
        aid=l.get("adb_id","")
        if not aid:continue
        if aid in verified:continue
        c=cur.get(aid,{})
        status=c.get("identity_status","")
        q=(l.get("wikidata_id") or c.get("wikidata_id") or "").strip()
        if not q:
            deterministic[aid]=c
        elif status=="no_primary_bazi_feature":
            deterministic[aid]=c
        else:
            retry_aids.add(aid)

    # Build a retry links file using the exact current link mapping.
    link_fields=list(links[0].keys()) if links else []
    retry_links=[r for r in links if r.get("adb_id") in retry_aids]
    Path(args.retry_links).parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(args.retry_links,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=link_fields);w.writeheader();w.writerows(retry_links)

    base_rows=list(verified.values())+list(deterministic.values())
    write(args.consensus_base,base_rows)
    report={
      "old_verified":sum(r.get("identity_status")=="verified_day_match" for r in old.values()),
      "current_verified":sum(r.get("identity_status")=="verified_day_match" for r in cur.values()),
      "verified_union":len(verified),
      "deterministic_no_retry":len(deterministic),
      "retry_adb_rows":len(retry_aids),
      "retry_unique_qids":len({r.get("wikidata_id") for r in retry_links if r.get("wikidata_id")}),
      "policy":"retain any prior verified_day_match; losslessly retry all remaining QID-bearing primary-feature rows"
    }
    Path(args.report).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

def finalize(args):
    base=by_adb(read_rows(args.consensus_base))
    retry=by_adb(read_rows(args.retry_validation))
    merged=dict(base);merged.update(retry)
    rows=[merged[k] for k in sorted(merged,key=lambda x:int(x) if x.isdigit() else x)]
    write(args.output,rows)
    counts={}
    for r in rows:
        s=r.get("identity_status","");counts[s]=counts.get(s,0)+1
    report={
      "rows":len(rows),
      "status_counts":counts,
      "verified_day_match":counts.get("verified_day_match",0),
      "retry_rows":len(retry),
      "rule":"historical positive verification is persistent; unresolved rows refreshed losslessly"
    }
    Path(args.report).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("prepare")
    p.add_argument("old_validation");p.add_argument("current_validation");p.add_argument("current_links")
    p.add_argument("retry_links");p.add_argument("consensus_base");p.add_argument("report")
    p.set_defaults(fn=prepare)
    p=sub.add_parser("finalize")
    p.add_argument("consensus_base");p.add_argument("retry_validation");p.add_argument("output");p.add_argument("report")
    p.set_defaults(fn=finalize)
    args=ap.parse_args();args.fn(args)
if __name__=="__main__":main()
