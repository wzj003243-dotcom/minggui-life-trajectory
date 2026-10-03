"""Normalize Wikidata birth assertions without inventing missing precision."""
from __future__ import annotations
import json, sys, uuid
from datetime import datetime
from pathlib import Path

PRECISION={9:"year",10:"month",11:"day",12:"hour",13:"minute",14:"exact"}

def parse_wikidata_time(value: str | None, precision: int | None):
    if not value: return None
    # Wikidata may contain years outside Python datetime; keep original if not safely parseable.
    raw=value.lstrip("+")
    date_part=raw.split("T",1)[0]
    bits=date_part.split("-")
    try:
        year=int(bits[0])
        month=int(bits[1]) if len(bits)>1 else 1
        day=int(bits[2]) if len(bits)>2 else 1
    except (ValueError,IndexError):
        return {"raw":value,"date_iso":None}
    if year<1 or year>9999:
        return {"raw":value,"date_iso":None}
    p=PRECISION.get(precision,"unknown")
    if p=="year": iso=f"{year:04d}"
    elif p=="month": iso=f"{year:04d}-{month:02d}"
    else: iso=f"{year:04d}-{month:02d}-{day:02d}"
    return {"raw":value,"date_iso":iso}

def main():
    src=Path(sys.argv[1] if len(sys.argv)>1 else "data/raw/wikidata/person_backbone.ndjson")
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/birth_assertions.ndjson")
    out.parent.mkdir(parents=True,exist_ok=True)
    with src.open(encoding="utf-8") as f, out.open("w",encoding="utf-8") as w:
        for line in f:
            person=json.loads(line)
            qid=person["wikidata_id"]
            assertions=person.get("birth_assertions",[])
            for i,a in enumerate(assertions):
                p=PRECISION.get(a.get("precision"),"unknown")
                parsed=parse_wikidata_time(a.get("time"),a.get("precision"))
                status="conflicting" if len(assertions)>1 else "single-source"
                row={
                    "assertion_id":f"wd:{qid}:birth:{i}",
                    "person_id":f"wd:{qid}",
                    "date_iso":parsed["date_iso"] if parsed else None,
                    "date_precision":p,
                    "time_local":None,
                    "time_known":p in ("hour","minute","exact"),
                    "timezone":None,
                    "timezone_confidence":None,
                    "place_id":("wd:"+person["birth_place_ids"][0]) if person.get("birth_place_ids") else None,
                    "latitude":None,"longitude":None,
                    "source_id":"wikidata",
                    "source_reliability":f"rank={a.get('rank')};refs={a.get('reference_count',0)}",
                    "source_confidence":None,
                    "status":status,
                    "notes":"Raw Wikidata time retained in source backbone; local birth time requires place/timezone normalization."
                }
                w.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(out)

if __name__=="__main__": main()
