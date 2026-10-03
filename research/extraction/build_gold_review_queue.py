"""Build an adjudication queue from biography timeline candidates.

Output keeps original evidence and adds blank review columns. It can be reviewed by a human or a
separate adjudication model, but accepted structured events must always point back to candidate_id.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random
from collections import defaultdict
from pathlib import Path

REVIEW_FIELDS=[
 "review_accept","review_event_type","review_date_start","review_date_end",
 "review_date_precision","review_confidence","review_notes","reviewer"
]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("candidates");ap.add_argument("output")
    ap.add_argument("--people",type=int,default=300);ap.add_argument("--max-per-person",type=int,default=8)
    ap.add_argument("--seed",type=int,default=20261003);args=ap.parse_args()
    by=defaultdict(list)
    with gzip.open(args.candidates,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);base=r.fieldnames or []
        for x in r:by[x["person_id"]].append(x)
    rng=random.Random(args.seed)
    pids=list(by);rng.shuffle(pids);pids=pids[:args.people]
    rows=[]
    for pid in pids:
        xs=by[pid]
        # diversity first: one per proposed domain combination, then fill randomly
        rng.shuffle(xs);seen=set();sel=[]
        for x in xs:
            key=x.get("candidate_domains","")
            if key not in seen:
                sel.append(x);seen.add(key)
            if len(sel)>=args.max_per_person:break
        if len(sel)<args.max_per_person:
            for x in xs:
                if x not in sel:sel.append(x)
                if len(sel)>=args.max_per_person:break
        rows.extend(sel)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=base+REVIEW_FIELDS
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for x in rows:
            y=dict(x);y.update({k:"" for k in REVIEW_FIELDS});wr.writerow(y)
    report={"people_selected":len({x["person_id"] for x in rows}),"candidate_rows":len(rows),
            "purpose":"gold adjudication queue; accepted events must retain candidate evidence provenance"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
