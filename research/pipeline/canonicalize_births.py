"""Canonicalize precision-aware Wikidata birth assertions for model use.

Primary eligibility requires:
- precision 11 (day)
- BHHT birth year agreement
- one unique day value after removing exact duplicate statements

We do not resolve genuine conflicting days by guessing. PreferredRank is reported but a
preferred statement only wins automatically when all preferred day-level values agree.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from pathlib import Path

def truthy(x):
    return str(x).lower() in ("true","1","yes")

def rank_name(uri):
    if not uri:return ""
    return uri.rsplit("#",1)[-1].replace("Rank","").lower()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("assertions")
    ap.add_argument("output")
    args=ap.parse_args()
    groups=defaultdict(list)
    with gzip.open(args.assertions,"rt",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            groups[row["wikidata_id"]].append(row)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["wikidata_id","birth_date","calendar_model","canonical_status","candidate_days",
            "statement_count","preferred_day_count","bhht_birth_year"]
    counts=defaultdict(int)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for q,rows in groups.items():
            day=[r for r in rows if str(r.get("time_precision"))=="11" and truthy(r.get("birth_year_match"))]
            # dedupe identical date/calendar pairs
            by_key={}
            for r in day:
                date=(r.get("birth_time_value") or "")[:10]
                cal=r.get("calendar_model") or ""
                by_key[(date,cal)]=r
            pref_keys={k for k,r in by_key.items() if rank_name(r.get("statement_rank"))=="preferred"}
            if pref_keys and len(pref_keys)==1:
                chosen_key=next(iter(pref_keys));status="canonical_preferred"
            elif len(by_key)==1:
                chosen_key=next(iter(by_key));status="canonical_unique"
            elif len(by_key)>1:
                chosen_key=None;status="conflicting_day_values"
            else:
                chosen_key=None
                has_month=any(str(r.get("time_precision"))=="10" for r in rows)
                has_year=any(str(r.get("time_precision"))=="9" for r in rows)
                status="month_only" if has_month else ("year_only" if has_year else "no_eligible_birth")
            counts[status]+=1
            wr.writerow({
              "wikidata_id":q,
              "birth_date":chosen_key[0] if chosen_key else "",
              "calendar_model":chosen_key[1] if chosen_key else "",
              "canonical_status":status,
              "candidate_days":"|".join(sorted({k[0] for k in by_key})),
              "statement_count":len(rows),
              "preferred_day_count":len(pref_keys),
              "bhht_birth_year":rows[0].get("bhht_birth_year","")
            })
    report={"people":len(groups),"statuses":dict(counts),
      "primary_canonical":counts["canonical_unique"]+counts["canonical_preferred"]}
    rp=out.with_name(out.name[:-7]+".report.json" if out.name.endswith(".csv.gz") else out.stem+".report.json")
    rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
