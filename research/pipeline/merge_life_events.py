"""Merge common-schema life-event gzip CSV tables, deduplicating by event_id."""
from __future__ import annotations
import argparse,csv,gzip,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output");ap.add_argument("inputs",nargs="+");args=ap.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    seen=set();rows=0;people=set();types={}
    writer=None
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        for raw in args.inputs:
            with gzip.open(raw,"rt",encoding="utf-8",newline="") as f:
                r=csv.DictReader(f)
                if writer is None:
                    writer=csv.DictWriter(w,fieldnames=r.fieldnames);writer.writeheader()
                elif r.fieldnames!=writer.fieldnames:
                    raise SystemExit(f"schema mismatch: {raw}")
                for row in r:
                    eid=row.get("event_id")
                    if not eid or eid in seen:continue
                    seen.add(eid);writer.writerow(row);rows+=1;people.add(row.get("person_id"))
                    et=row.get("event_type") or "";types[et]=types.get(et,0)+1
    report={"event_rows":rows,"people":len(people),"event_type_counts":dict(sorted(types.items(),key=lambda x:(-x[1],x[0])))}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
