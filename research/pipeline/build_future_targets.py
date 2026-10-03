"""Build standardized future-event targets from cutoff snapshots.

This script deliberately knows nothing about BaZi. It defines the labels that *all* models
(reality-only, BaZi-only, mixed) must predict.
"""
from __future__ import annotations
import json, sys
from calendar import monthrange
from datetime import date
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def parse_date(s):
    if not s: return None
    try:
        b=s[:10].split("-")
        if len(b)==1: return date(int(b[0]),12,31)
        if len(b)==2: return date(int(b[0]),int(b[1]),monthrange(int(b[0]),int(b[1]))[1])
        return date.fromisoformat(s[:10])
    except Exception:
        return None

def add_years(d: date, years: int):
    try: return d.replace(year=d.year+years)
    except ValueError: return d.replace(month=2,day=28,year=d.year+years)

def main():
    if len(sys.argv)<3:
        raise SystemExit("usage: build_future_targets.py snapshots.ndjson events.ndjson [targets.json] [output]")
    snapshots=list(load(sys.argv[1]))
    events=list(load(sys.argv[2]))
    spec_path=Path(sys.argv[3]) if len(sys.argv)>3 else Path("data/ontology/targets.v1.json")
    out=Path(sys.argv[4]) if len(sys.argv)>4 else Path("data/processed/future_targets.ndjson")
    spec=json.loads(spec_path.read_text(encoding="utf-8"))
    by_person={}
    for e in events: by_person.setdefault(e["person_id"],[]).append(e)
    out.parent.mkdir(parents=True,exist_ok=True)
    n=0
    with out.open("w",encoding="utf-8") as w:
        for s in snapshots:
            cutoff=parse_date(s["information_cutoff"])
            if not cutoff: continue
            person_events=by_person.get(s["person_id"],[])
            for t in spec["targets"]:
                allowed=set(t["event_types"])
                for horizon in t["horizons_years"]:
                    end=add_years(cutoff,horizon)
                    hits=[]
                    for e in person_events:
                        if e["event_type"] not in allowed: continue
                        occurred=parse_date(e.get("start_date") or e.get("end_date"))
                        if occurred and cutoff < occurred <= end:
                            hits.append(e["event_id"])
                    row={
                        "target_id":f"{s['snapshot_id']}:{t['name']}:{horizon}y",
                        "person_id":s["person_id"],
                        "information_cutoff":cutoff.isoformat(),
                        "horizon_start":cutoff.isoformat(),
                        "horizon_end":end.isoformat(),
                        "target_spec_version":spec["version"],
                        "target_name":f"{t['name']}__{horizon}y",
                        "value":bool(hits),
                        "supporting_event_ids":hits,
                        "label_confidence":1.0 if hits else 0.8
                    }
                    w.write(json.dumps(row,ensure_ascii=False)+"\n"); n+=1
    print(f"wrote {n:,} targets -> {out}")

if __name__=="__main__": main()
