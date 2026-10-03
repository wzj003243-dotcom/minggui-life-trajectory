"""Attach resolved birth-place coordinates to birth assertions when directly available.

Coordinates are useful as reality/geography controls. They are NOT used to invent a
historical birth timezone or precise birth hour.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

def load(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def main():
    if len(sys.argv)<3:
        raise SystemExit("usage: enrich_birth_places.py births.ndjson entity_lookup.ndjson [output]")
    births=Path(sys.argv[1]); lookup=Path(sys.argv[2])
    out=Path(sys.argv[3]) if len(sys.argv)>3 else Path("data/processed/birth_assertions_places.ndjson")
    entities={f"wd:{e['wikidata_id']}":e for e in load(lookup)}
    out.parent.mkdir(parents=True,exist_ok=True)
    with births.open(encoding="utf-8") as f, out.open("w",encoding="utf-8") as w:
        for line in f:
            b=json.loads(line)
            ent=entities.get(b.get("place_id"))
            coord=ent.get("coordinates") if ent else None
            if coord:
                b["latitude"]=coord.get("lat")
                b["longitude"]=coord.get("lng")
                b["notes"]=((b.get("notes") or "")+" direct_place_coordinate=wikidata:P625").strip()
            w.write(json.dumps(b,ensure_ascii=False)+"\n")
    print(out)

if __name__=="__main__": main()
