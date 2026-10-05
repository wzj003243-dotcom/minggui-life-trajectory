"""Regression smoke for LifeGraph effective-point and yearly-state semantics."""
from __future__ import annotations
import csv,gzip,json,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write_gz(path,fields,rows):
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        cohort=d/"cohort.csv.gz"
        write_gz(cohort,["wikidata_id"],[{"wikidata_id":"Q1"}])

        fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max","age_mid","source_id","observable_from"]
        rows=[
          {"event_id":"w1","person_id":"Q1","domain":"creation","event_type":"creation.scholar_work","event_date_min":"2000-01-01","event_date_max":"2000-01-01","age_mid":"30","source_id":"openalex","observable_from":"2000-01-01"},
          {"event_id":"w2","person_id":"Q1","domain":"creation","event_type":"creation.scholar_work","event_date_min":"2000-02-01","event_date_max":"2000-02-01","age_mid":"30.1","source_id":"openalex","observable_from":"2000-02-01"},
          {"event_id":"w3","person_id":"Q1","domain":"creation","event_type":"creation.scholar_work","event_date_min":"2000-03-01","event_date_max":"2000-03-01","age_mid":"30.2","source_id":"openalex","observable_from":"2000-03-01"},
          {"event_id":"c1","person_id":"Q1","domain":"career","event_type":"career.position.start","event_date_min":"2000-04-01","event_date_max":"2000-04-01","age_mid":"30.3","source_id":"wikidata","observable_from":"2000-04-01"},
          {"event_id":"r1","person_id":"Q1","domain":"recognition","event_type":"recognition.award","event_date_min":"2001-05-01","event_date_max":"2001-05-01","age_mid":"31.3","source_id":"wikidata","observable_from":"2001-05-01"},
        ]
        events=d/"events.csv.gz";write_gz(events,fields,rows)

        coverage=d/"coverage.json"
        subprocess.run([sys.executable,str(ROOT/"research/quality/lifegraph_coverage_report.py"),str(coverage),str(events),"--cohort",str(cohort)],check=True,cwd=ROOT)
        cov=json.loads(coverage.read_text())
        p=cov["people"][0]
        assert p["event_count"]==5,p
        assert p["effective_event_points"]==3,p  # 3 papers in 2000 collapse to 1 + career + recognition

        states=d/"states.csv.gz"
        subprocess.run([sys.executable,str(ROOT/"research/pipeline/build_lifegraph_year_states.py"),str(events),str(states)],check=True,cwd=ROOT)
        with gzip.open(states,"rt",encoding="utf-8",newline="") as f:
            data={int(r["year"]):r for r in csv.DictReader(f)}
        assert int(data[2000]["events_this_year"])==4,data[2000]
        assert int(data[2000]["effective_points_this_year"])==2,data[2000]
        assert int(data[2000]["effective_year_count__creation"])==1,data[2000]
        assert int(data[2001]["cumulative_effective_points"])==3,data[2001]
        assert int(data[2001]["cumulative_source_family_breadth"])==2,data[2001]
    print("lifegraph state smoke OK")

if __name__=="__main__":main()
