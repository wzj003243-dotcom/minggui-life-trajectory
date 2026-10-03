"""Regression smoke tests for normalized QID fields and start/end event expansion."""
from __future__ import annotations
import csv,gzip,json,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write_gz(path,fields,rows):
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def read_gz(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def main():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        cohort=d/"cohort.csv.gz"
        write_gz(cohort,["wikidata_id","birth","ranking_visib_5criteria"],[
          {"wikidata_id":"Q42","birth":"1952","ranking_visib_5criteria":"1"},
          {"wikidata_id":"Q1","birth":"1900","ranking_visib_5criteria":"2"},
        ])
        sys.path.insert(0,str(ROOT))
        from research.acquire.fetch_wikidata_birth_assertions import read_candidates
        got=read_candidates(cohort,0)
        assert [x[1] for x in got]==["Q42","Q1"],got

        births=d/"births.csv.gz"
        write_gz(births,["wikidata_id","birth_date","canonical_status"],[
          {"wikidata_id":"Q42","birth_date":"1952-03-11","canonical_status":"canonical_unique"}
        ])
        claims=d/"claims.csv.gz"
        fields=["person_id","rodden_rating","property","event_type","statement_id","value_qid","rank","reference_count","start_json","end_json","point_json"]
        start=json.dumps([{"time":"+1980-01-01T00:00:00Z","precision":11,"calendar_model":"http://www.wikidata.org/entity/Q1985727"}])
        end=json.dumps([{"time":"+1990-12-31T00:00:00Z","precision":11,"calendar_model":"http://www.wikidata.org/entity/Q1985727"}])
        write_gz(claims,fields,[{"person_id":"Q42","rodden_rating":"","property":"P108","event_type":"career.employer",
          "statement_id":"s1","value_qid":"Q99","rank":"normal","reference_count":"2","start_json":start,"end_json":end,"point_json":"[]"}])
        out=d/"events.csv.gz"
        subprocess.run([sys.executable,str(ROOT/"research/pipeline/claims_to_life_events.py"),str(claims),str(births),str(out)],check=True,cwd=ROOT)
        events=read_gz(out)
        assert {e["qualifier_kind"] for e in events}=={"start","end"},events
        assert {e["event_type"] for e in events}=={"career.employer.start","career.employer.end"},events
    print("event pipeline smoke OK")

if __name__=="__main__":main()
