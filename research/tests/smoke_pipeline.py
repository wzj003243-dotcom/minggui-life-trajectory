"""Dependency-free smoke test for cutoff/target/leakage semantics."""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write(path, rows):
    path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        births=d/"births.ndjson"; events=d/"events.ndjson"; snaps=d/"snaps.ndjson"; targets=d/"targets.ndjson"
        write(births,[{
          "assertion_id":"test:b1","person_id":"test:p1","date_iso":"2000-01-01","date_precision":"day",
          "time_local":None,"time_known":False,"timezone":None,"timezone_confidence":None,"place_id":None,
          "latitude":None,"longitude":None,"source_id":"fixture","source_reliability":None,"source_confidence":1,
          "status":"single-source","notes":None
        }])
        write(events,[
          {"event_id":"e1","person_id":"test:p1","domain":"education","event_type":"education.start","start_date":"2018-09-01","end_date":None,"age_start":None,"age_end":None,"temporal_precision":"day","location_id":None,"organization_id":None,"subject_id":None,"magnitude":None,"visibility":"unknown","description_normalized":None,"source_id":"fixture","extraction_method":"human","confidence":1,"observable_from":"2018-09-01","attributes":{}},
          {"event_id":"e2","person_id":"test:p1","domain":"migration","event_type":"migration.cross_country","start_date":"2027-06-01","end_date":None,"age_start":None,"age_end":None,"temporal_precision":"day","location_id":None,"organization_id":None,"subject_id":None,"magnitude":None,"visibility":"unknown","description_normalized":None,"source_id":"fixture","extraction_method":"human","confidence":1,"observable_from":"2027-06-01","attributes":{}}
        ])
        subprocess.run([sys.executable,str(ROOT/"research/pipeline/build_cutoff_snapshots.py"),str(births),str(events),str(snaps)],check=True,cwd=ROOT)
        subprocess.run([sys.executable,str(ROOT/"research/quality/leakage_audit.py"),str(snaps),str(events)],check=True,cwd=ROOT)
        subprocess.run([sys.executable,str(ROOT/"research/pipeline/build_future_targets.py"),str(snaps),str(events),str(ROOT/"data/ontology/targets.v1.json"),str(targets)],check=True,cwd=ROOT)
        snapshots=[json.loads(x) for x in snaps.read_text().splitlines()]
        age25=next(x for x in snapshots if x["cutoff_age"]==25)
        assert "e1" in age25["included_event_ids"] and "e2" not in age25["included_event_ids"]
        t=[json.loads(x) for x in targets.read_text().splitlines()]
        mig=next(x for x in t if x["target_id"].startswith("test:p1:age:25:migration_cross_country:5y"))
        assert mig["value"] is True and mig["supporting_event_ids"]==["e2"]
    print("smoke pipeline OK")

if __name__=="__main__": main()
