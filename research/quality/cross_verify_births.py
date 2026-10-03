"""Cross-verify birth assertions without erasing disagreements.

The script groups assertions by person and comparable date value. Agreement across
independent source ids upgrades status to cross-verified. Competing values remain conflicting.
A future version can use source-record independence_group instead of source_id.
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def comparable(a):
    value=a.get("date_iso")
    p=a.get("date_precision")
    if not value: return None
    if p=="year": return value[:4]
    if p=="month": return value[:7]
    return value[:10]

def main():
    src=Path(sys.argv[1]); out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/birth_assertions_verified.ndjson")
    by_person=defaultdict(list)
    for a in load(src): by_person[a["person_id"]].append(a)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8") as w:
        for pid,rows in by_person.items():
            values=defaultdict(set)
            for a in rows:
                c=comparable(a)
                if c: values[c].add(a["source_id"])
            competing=[k for k,v in values.items() if v]
            for a in rows:
                c=comparable(a)
                independent=len(values.get(c,set()))
                if len(competing)>1:
                    a["status"]="conflicting"
                elif independent>=2:
                    a["status"]="cross-verified"
                else:
                    a["status"]="single-source"
                a["notes"]=((a.get("notes") or "")+f" cross_verify_sources={independent}").strip()
                w.write(json.dumps(a,ensure_ascii=False)+"\n")
    print(out)

if __name__=="__main__": main()
