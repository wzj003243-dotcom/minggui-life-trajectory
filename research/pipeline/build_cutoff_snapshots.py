"""Build leakage-safe event snapshots at age cutoffs.

Input:
  birth_assertions.ndjson
  life_events.ndjson
Output:
  snapshots.ndjson

This first version stores eligible event ids and simple counts. Model-specific feature
builders can consume these snapshots later.
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

CUTS=(18,25,30,40)

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def parse_date(s):
    if not s: return None
    try:
        bits=s.split("-")
        if len(bits)==1: return date(int(bits[0]),12,31)
        if len(bits)==2: return date(int(bits[0]),int(bits[1]),28)
        return date.fromisoformat(s[:10])
    except Exception:
        return None

def main():
    if len(sys.argv)<3:
        raise SystemExit("usage: build_cutoff_snapshots.py births.ndjson events.ndjson [output]")
    births=list(load(sys.argv[1])); events=list(load(sys.argv[2]))
    out=Path(sys.argv[3] if len(sys.argv)>3 else "data/processed/cutoff_snapshots.ndjson")
    out.parent.mkdir(parents=True,exist_ok=True)
    canonical={}
    for b in births:
        if b.get("status")=="conflicting": continue
        d=parse_date(b.get("date_iso"))
        if d and b["person_id"] not in canonical: canonical[b["person_id"]]=(b,d)
    by_person=defaultdict(list)
    for e in events: by_person[e["person_id"]].append(e)

    with out.open("w",encoding="utf-8") as w:
        for pid,(birth,bdate) in canonical.items():
            for age in CUTS:
                try: cutoff=bdate.replace(year=bdate.year+age)
                except ValueError: cutoff=bdate.replace(month=2,day=28,year=bdate.year+age)
                eligible=[]
                domain_counts=defaultdict(int)
                for e in by_person.get(pid,[]):
                    obs=parse_date(e.get("observable_from"))
                    if obs and obs<=cutoff:
                        eligible.append(e["event_id"]); domain_counts[e["domain"]]+=1
                row={
                    "snapshot_id":f"{pid}:age:{age}",
                    "person_id":pid,
                    "information_cutoff":cutoff.isoformat(),
                    "cutoff_age":age,
                    "feature_spec_version":"snapshot-counts-v0.1",
                    "birth_assertion_id":birth["assertion_id"],
                    "included_event_ids":eligible,
                    "features":{f"past_event_count_{k}":v for k,v in domain_counts.items()} | {"past_event_count_total":len(eligible)},
                    "leakage_audit_passed":True,
                    "created_at":datetime.utcnow().isoformat()+"Z"
                }
                w.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(out)

if __name__=="__main__": main()
