"""Verify that a feature snapshot never includes an event observable after its cutoff."""
from __future__ import annotations
import json, sys
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def main():
    if len(sys.argv)<3: raise SystemExit("usage: leakage_audit.py snapshots.ndjson events.ndjson")
    events={e["event_id"]:e for e in load(sys.argv[2])}
    failures=[]
    checked=0
    for s in load(sys.argv[1]):
        cutoff=s["information_cutoff"]
        for eid in s.get("included_event_ids",[]):
            checked+=1
            e=events.get(eid)
            if not e:
                failures.append((s["snapshot_id"],eid,"missing-event")); continue
            obs=e.get("observable_from")
            if not obs:
                failures.append((s["snapshot_id"],eid,"missing-observable-from"))
            elif obs[:10] > cutoff[:10]:
                failures.append((s["snapshot_id"],eid,f"future:{obs}>{cutoff}"))
    print(json.dumps({"checked_links":checked,"failures":len(failures),"examples":failures[:25]},ensure_ascii=False,indent=2))
    raise SystemExit(1 if failures else 0)

if __name__=="__main__": main()
