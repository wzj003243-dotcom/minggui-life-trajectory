"""Convert temporally-qualified Wikidata statements into MingGui life-event candidates.

This does not claim every statement is a true "event". It produces auditable candidates
that can later be deduplicated/adjudicated against biographies and other sources.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

PRECISION={9:"year",10:"month",11:"day",12:"day",13:"day",14:"day"}

def compact_date(t: dict | None):
    if not t or not t.get("time"): return None, "unknown"
    raw=t["time"].lstrip("+").split("T",1)[0]
    bits=raw.split("-")
    try:
        y=int(bits[0]); m=int(bits[1]) if len(bits)>1 else 1; d=int(bits[2]) if len(bits)>2 else 1
    except (ValueError,IndexError):
        return None,"unknown"
    p=PRECISION.get(t.get("precision"),"unknown")
    if y < 1 or y > 9999: return None,p
    if p=="year": return f"{y:04d}",p
    if p=="month": return f"{y:04d}-{m:02d}",p
    return f"{y:04d}-{m:02d}-{d:02d}",p

def first(xs):
    return xs[0] if xs else None

def visibility_for(kind: str):
    if kind.startswith(("career.","organization.","recognition.","education.")): return "unknown"
    return "unknown"

def main():
    src=Path(sys.argv[1] if len(sys.argv)>1 else "data/raw/wikidata/person_backbone.ndjson")
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/wikidata_event_candidates.ndjson")
    out.parent.mkdir(parents=True,exist_ok=True)
    n=0
    with src.open(encoding="utf-8") as f, out.open("w",encoding="utf-8") as w:
        for line in f:
            p=json.loads(line)
            pid=f"wd:{p['wikidata_id']}"
            for i,s in enumerate(p.get("structured_statements",[])):
                point,point_p=compact_date(first(s.get("point_times",[])))
                start,start_p=compact_date(first(s.get("start_times",[])))
                end,end_p=compact_date(first(s.get("end_times",[])))
                if point:
                    start=end=point
                    precision=point_p
                else:
                    precision=start_p if start else end_p
                if not (start or end):
                    # Keep undated structured facts in source data, but do not turn them into
                    # timeline events because they cannot support cutoff-aware prediction.
                    continue
                typ=s["semantic_type"]
                row={
                    "event_id":f"wd:{p['wikidata_id']}:{s.get('statement_id') or i}",
                    "person_id":pid,
                    "domain":typ.split(".",1)[0],
                    "event_type":typ,
                    "start_date":start,
                    "end_date":end,
                    "age_start":None,"age_end":None,
                    "temporal_precision":precision if precision in {"year","month","day"} else "unknown",
                    "location_id":None,
                    "organization_id":("wd:"+s["value_qid"]) if typ.startswith(("career.","organization.","education.")) else None,
                    "subject_id":"wd:"+s["value_qid"],
                    "magnitude":None,
                    "visibility":visibility_for(typ),
                    "description_normalized":None,
                    "source_id":"wikidata",
                    "extraction_method":"structured",
                    "confidence":min(0.95,0.58+0.07*min(s.get("reference_count",0),5)+(0.08 if s.get("rank")=="preferred" else 0)),
                    "observable_from":start or end,
                    "attributes":{"property":s["property"],"rank":s.get("rank"),"reference_count":s.get("reference_count",0)}
                }
                w.write(json.dumps(row,ensure_ascii=False)+"\n"); n+=1
    print(f"wrote {n:,} dated structured event candidates -> {out}")

if __name__=="__main__": main()
