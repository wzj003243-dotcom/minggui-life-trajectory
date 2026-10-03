"""Basic data-quality audit for normalized birth assertions and life-event NDJSON."""
from __future__ import annotations
import json, sys
from collections import Counter,defaultdict
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def audit_births(path):
    counts=Counter(); people=defaultdict(list)
    for x in load(path):
        counts["rows"]+=1
        counts["precision:"+x.get("date_precision","unknown")]+=1
        counts["status:"+x.get("status","unknown")]+=1
        people[x["person_id"]].append(x)
    counts["people"]=len(people)
    counts["people_multiple_assertions"]=sum(len(v)>1 for v in people.values())
    counts["time_known"]=sum(bool(x.get("time_known")) for vals in people.values() for x in vals)
    return counts

def audit_events(path):
    counts=Counter()
    per_person=defaultdict(list)
    for e in load(path):
        counts["rows"]+=1
        counts["domain:"+e["domain"]]+=1
        counts["precision:"+e["temporal_precision"]]+=1
        if e.get("confidence",0)<0.6: counts["low_confidence"]+=1
        if not e.get("observable_from"): counts["missing_observable_from"]+=1
        per_person[e["person_id"]].append(e)
    counts["people"]=len(per_person)
    return counts

def main():
    if len(sys.argv)<2: raise SystemExit("births path required; optional events path")
    print(json.dumps(audit_births(sys.argv[1]),indent=2,ensure_ascii=False))
    if len(sys.argv)>2:
        print(json.dumps(audit_events(sys.argv[2]),indent=2,ensure_ascii=False))

if __name__=="__main__": main()
