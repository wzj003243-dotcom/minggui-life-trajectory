"""Regression test: recanonicalization must preserve inherited source_families."""
from __future__ import annotations
import csv,gzip,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        src=d/"in.csv.gz";out=d/"out.csv.gz"
        fields=["canonical_event_id","person_id","domain","event_family","event_type","event_date_min","event_date_max",
                "temporal_precision","age_min","age_max","age_mid","subject_id","source_families","source_count",
                "evidence_row_count","confidence_max","observable_from","member_event_ids","member_sources"]
        with gzip.open(src,"wt",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({
              "canonical_event_id":"lg:test","person_id":"Q1","domain":"career","event_family":"career.role_start",
              "event_type":"career.position.start","event_date_min":"2000-01-01","event_date_max":"2000-01-01",
              "temporal_precision":"day","age_min":"20","age_max":"20","age_mid":"20","subject_id":"Q2",
              "source_families":"wikidata","source_count":"1","evidence_row_count":"1","confidence_max":"0.9",
              "observable_from":"2000-01-01","member_event_ids":"e1","member_sources":"wikidata"
            })
        subprocess.run([sys.executable,str(ROOT/"research/pipeline/canonicalize_lifegraph_events.py"),str(out),str(src)],check=True,cwd=ROOT)
        with gzip.open(out,"rt",encoding="utf-8",newline="") as f:
            rows=list(csv.DictReader(f))
        assert len(rows)==1,rows
        assert rows[0]["source_families"]=="wikidata",rows[0]
        assert rows[0]["source_count"]=="1",rows[0]
    print("source-family recanonicalization smoke OK")

if __name__=="__main__":main()
