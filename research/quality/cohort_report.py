"""Generate compact coverage diagnostics for a MingGui cohort."""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def main():
    if len(sys.argv)<3:
        raise SystemExit("usage: cohort_report.py births.ndjson events.ndjson")
    births=list(load(sys.argv[1])); events=list(load(sys.argv[2]))
    persons={b["person_id"] for b in births}
    bc=Counter(b.get("date_precision","unknown") for b in births)
    bs=Counter(b.get("status","unknown") for b in births)
    ev=Counter(e.get("domain","unknown") for e in events)
    per=Counter(e["person_id"] for e in events)
    report={
      "people_with_birth_assertions":len(persons),
      "birth_assertion_rows":len(births),
      "birth_precision":dict(bc),
      "birth_status":dict(bs),
      "event_rows":len(events),
      "event_domains":dict(ev),
      "people_with_events":len(per),
      "people_with_2plus_events":sum(v>=2 for v in per.values()),
      "people_with_5plus_events":sum(v>=5 for v in per.values()),
      "median_events_per_eventful_person":None
    }
    vals=sorted(per.values())
    if vals: report["median_events_per_eventful_person"]=vals[len(vals)//2]
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
