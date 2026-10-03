"""Select a diverse Gold-300 cohort for manual/adjudicated life-event validation.

Uses round-robin sampling over available demographic/context strata instead of pure fame ranking.
Input may be a BHHT-derived cohort or another CSV.gz containing some of:
  un_region, level1_main_occ, birth_era, gender, wikipedia_edition_tier
"""
from __future__ import annotations
import argparse,csv,gzip,json,random
from collections import defaultdict
from pathlib import Path

DIMS=("un_region","level1_main_occ","birth_era","gender","wikipedia_edition_tier")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--target",type=int,default=300);ap.add_argument("--seed",type=int,default=20261003)
    ap.add_argument("--id-column",default="wikidata_id");args=ap.parse_args()
    with gzip.open(args.input,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames or [];rows=list(r)
    dims=[d for d in DIMS if d in fields]
    rng=random.Random(args.seed)
    buckets=defaultdict(list)
    for row in rows:
        pid=(row.get(args.id_column) or "").strip()
        if not pid:continue
        key=tuple((row.get(d) or "unknown").strip() or "unknown" for d in dims)
        buckets[key].append(row)
    for xs in buckets.values():rng.shuffle(xs)
    keys=list(buckets);rng.shuffle(keys)
    chosen=[];used=set()
    while len(chosen)<args.target:
        progress=False
        for k in keys:
            if len(chosen)>=args.target:break
            while buckets[k]:
                x=buckets[k].pop()
                pid=x.get(args.id_column)
                if pid in used:continue
                chosen.append(x);used.add(pid);progress=True;break
        if not progress:break
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader();wr.writerows(chosen)
    report={"target":args.target,"selected":len(chosen),"input_rows":len(rows),"stratification_dims":dims,
            "represented_strata":len({tuple((x.get(d) or "unknown") for d in dims) for x in chosen})}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
