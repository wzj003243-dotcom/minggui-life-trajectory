"""Select a profession-targeted cohort from BHHT normalized CSV.gz.

Searches level1/level2/level3 occupation text using case-insensitive keywords, then keeps a
stable, diversity-preserving sample across region and birth era when available.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,re
from collections import defaultdict
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--keywords",required=True,help="comma-separated regex fragments")
    ap.add_argument("--target",type=int,default=2000)
    ap.add_argument("--seed",type=int,default=20261004)
    args=ap.parse_args()
    pats=[re.compile(x.strip(),re.I) for x in args.keywords.split(",") if x.strip()]
    with gzip.open(args.input,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames or [];rows=list(r)
    occ_cols=[c for c in ("level1_main_occ","level2_main_occ","level3_main_occ") if c in fields]
    eligible=[]
    for x in rows:
        txt=" | ".join(x.get(c,"") or "" for c in occ_cols)
        if any(p.search(txt) for p in pats):eligible.append(x)
    rng=random.Random(args.seed)
    buckets=defaultdict(list)
    for x in eligible:
        key=(x.get("un_region") or "unknown",x.get("birth_era") or "unknown")
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
                q=(x.get("wikidata_id") or x.get("wikidata_code") or "").strip()
                if not q or q in seen:continue
                chosen.append(x);seen.add(q);progress=True;break
        if not progress:break
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader();wr.writerows(chosen)
    report={"input_rows":len(rows),"eligible_rows":len(eligible),"selected":len(chosen),
            "keywords":[p.pattern for p in pats],"occupation_columns":occ_cols}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
