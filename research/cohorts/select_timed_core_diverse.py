"""Select a diverse subset from the verified timed core for biography enrichment."""
from __future__ import annotations
import argparse,csv,gzip,json,random
from collections import defaultdict
from pathlib import Path

def decade(v):
    try:return str((int(v[:4])//10)*10)
    except:return "unknown"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--target",type=int,default=600)
    ap.add_argument("--seed",type=int,default=20261005)
    args=ap.parse_args()
    with gzip.open(args.input,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames or [];rows=list(r)
    rng=random.Random(args.seed)
    buckets=defaultdict(list)
    for x in rows:
        q=(x.get("wikidata_id") or "").strip()
        if not q:continue
        key=(decade(x.get("birth_date_normalized") or ""),x.get("gender") or "unknown",x.get("birth_country") or "unknown")
        buckets[key].append(x)
    for xs in buckets.values():rng.shuffle(xs)
    keys=list(buckets);rng.shuffle(keys)
    chosen=[];seen=set()
    while len(chosen)<args.target:
        progress=False
        for k in keys:
            if len(chosen)>=args.target:break
            while buckets[k]:
                x=buckets[k].pop()
                q=x["wikidata_id"]
                if q in seen:continue
                chosen.append(x);seen.add(q);progress=True;break
        if not progress:break
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader();wr.writerows(chosen)
    report={"input_rows":len(rows),"selected":len(chosen),"represented_strata":len({
      (decade(x.get("birth_date_normalized") or ""),x.get("gender") or "unknown",x.get("birth_country") or "unknown")
      for x in chosen
    })}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
