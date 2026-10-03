"""Stream a local Wikidata JSON dump into a narrow MingGui person backbone.

Why a dump?
Wikidata recommends dumps rather than WDQS when the desired result set is very large.
This parser preserves birth time precision and multiple source claims instead of flattening
everything into one date.

Input examples:
  latest-all.json.bz2
  latest-all.json.gz
  latest-all.json

Output:
  data/raw/wikidata/person_backbone.ndjson

No third-party Python dependencies are required.
"""
from __future__ import annotations
import bz2, gzip, json, sys
from pathlib import Path
from typing import Iterable, TextIO

KEEP_PROPERTIES = ["P31","P569","P570","P19","P21","P27","P106","P69","P166"]

def open_text(path: Path) -> TextIO:
    if path.suffix == ".bz2":
        return bz2.open(path, "rt", encoding="utf-8")
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")

def qids_from_claim(entity: dict, prop: str) -> list[str]:
    out=[]
    for claim in entity.get("claims",{}).get(prop,[]):
        value=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(value,dict) and value.get("entity-type")=="item":
            qid=value.get("id")
            if qid: out.append(qid)
    return sorted(set(out))

def time_assertions(entity: dict, prop: str) -> list[dict]:
    rows=[]
    for claim in entity.get("claims",{}).get(prop,[]):
        snak=claim.get("mainsnak",{})
        dv=snak.get("datavalue",{})
        value=dv.get("value")
        if not isinstance(value,dict) or "time" not in value:
            continue
        rows.append({
            "time":value.get("time"),
            "precision":value.get("precision"),
            "calendar_model":value.get("calendarmodel"),
            "rank":claim.get("rank"),
            "reference_count":len(claim.get("references",[])),
            "statement_id":claim.get("id"),
        })
    return rows

def label(entity: dict, lang: str) -> str | None:
    return entity.get("labels",{}).get(lang,{}).get("value")

def is_human(entity: dict) -> bool:
    return "Q5" in qids_from_claim(entity,"P31")

def compact(entity: dict) -> dict:
    return {
        "wikidata_id":entity["id"],
        "name_en":label(entity,"en"),
        "name_zh":label(entity,"zh"),
        "birth_assertions":time_assertions(entity,"P569"),
        "death_assertions":time_assertions(entity,"P570"),
        "birth_place_ids":qids_from_claim(entity,"P19"),
        "gender_ids":qids_from_claim(entity,"P21"),
        "citizenship_ids":qids_from_claim(entity,"P27"),
        "occupation_ids":qids_from_claim(entity,"P106"),
        "education_ids":qids_from_claim(entity,"P69"),
        "award_ids":qids_from_claim(entity,"P166"),
    }

def iter_entities(f: Iterable[str]):
    for raw in f:
        line=raw.strip()
        if not line or line in ("[","]"): continue
        if line.endswith(","): line=line[:-1]
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue

def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: python research/ingest/wikidata_dump_extract.py /path/to/latest-all.json.bz2 [output]")
    src=Path(sys.argv[1])
    out=Path(sys.argv[2]) if len(sys.argv)>2 else Path("data/raw/wikidata/person_backbone.ndjson")
    out.parent.mkdir(parents=True,exist_ok=True)
    seen=written=0
    with open_text(src) as f, out.open("w",encoding="utf-8") as w:
        for entity in iter_entities(f):
            seen+=1
            if entity.get("type")!="item" or not is_human(entity): continue
            row=compact(entity)
            if not row["birth_assertions"]: continue
            w.write(json.dumps(row,ensure_ascii=False)+"\n")
            written+=1
            if written%100000==0: print(f"written={written:,} scanned={seen:,}",file=sys.stderr)
    print(f"done: {written:,} human records with birth assertions -> {out}")

if __name__=="__main__":
    main()
