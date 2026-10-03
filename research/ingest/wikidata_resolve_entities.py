"""Second-pass resolver for QIDs referenced by the person backbone.

Pass 1 extracts people and keeps referenced QIDs.
Pass 2 scans the same Wikidata dump and writes a compact entity lookup for only those QIDs.

This avoids loading the full knowledge graph into memory and gives us stable labels,
coordinates, country/timezone hints, and class hierarchy edges for places/occupations/
organizations/education institutions.
"""
from __future__ import annotations
import bz2, gzip, json, sys
from pathlib import Path

def open_text(path: Path):
    if path.suffix==".bz2": return bz2.open(path,"rt",encoding="utf-8")
    if path.suffix==".gz": return gzip.open(path,"rt",encoding="utf-8")
    return path.open("r",encoding="utf-8")

def iter_entities(f):
    for raw in f:
        line=raw.strip()
        if not line or line in ("[","]"): continue
        if line.endswith(","): line=line[:-1]
        try: yield json.loads(line)
        except json.JSONDecodeError: continue

def qid_from_snak(snak):
    v=snak.get("datavalue",{}).get("value")
    return v.get("id") if isinstance(v,dict) and v.get("entity-type")=="item" else None

def qids(entity,prop):
    return sorted({q for c in entity.get("claims",{}).get(prop,[]) if (q:=qid_from_snak(c.get("mainsnak",{})))})

def first_coordinate(entity):
    for c in entity.get("claims",{}).get("P625",[]):
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "latitude" in v:
            return {"lat":v.get("latitude"),"lng":v.get("longitude"),"precision":v.get("precision")}
    return None

def gather_wanted(person_backbone: Path):
    wanted=set()
    with person_backbone.open(encoding="utf-8") as f:
        for line in f:
            p=json.loads(line)
            for key in ("birth_place_ids","gender_ids","citizenship_ids","occupation_ids","education_ids","award_ids"):
                wanted.update(p.get(key,[]))
            for s in p.get("structured_statements",[]):
                if s.get("value_qid"): wanted.add(s["value_qid"])
    return wanted

def label(e,lang):
    return e.get("labels",{}).get(lang,{}).get("value")

def main():
    if len(sys.argv)<3:
        raise SystemExit("usage: wikidata_resolve_entities.py person_backbone.ndjson latest-all.json.bz2 [output]")
    people=Path(sys.argv[1]); dump=Path(sys.argv[2])
    out=Path(sys.argv[3]) if len(sys.argv)>3 else Path("data/raw/wikidata/entity_lookup.ndjson")
    wanted=gather_wanted(people)
    print(f"need to resolve {len(wanted):,} QIDs",file=sys.stderr)
    out.parent.mkdir(parents=True,exist_ok=True)
    found=0
    with open_text(dump) as f, out.open("w",encoding="utf-8") as w:
        for e in iter_entities(f):
            qid=e.get("id")
            if qid not in wanted: continue
            row={
              "wikidata_id":qid,
              "label_en":label(e,"en"),
              "label_zh":label(e,"zh"),
              "description_en":e.get("descriptions",{}).get("en",{}).get("value"),
              "coordinates":first_coordinate(e),
              "country_ids":qids(e,"P17"),
              "timezone_ids":qids(e,"P421"),
              "admin_parent_ids":qids(e,"P131"),
              "instance_of_ids":qids(e,"P31"),
              "subclass_of_ids":qids(e,"P279")
            }
            w.write(json.dumps(row,ensure_ascii=False)+"\n")
            found+=1
            if found==len(wanted): break
    print(f"resolved {found:,}/{len(wanted):,} -> {out}")

if __name__=="__main__": main()
