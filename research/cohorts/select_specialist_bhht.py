"""Select a profession-targeted BHHT cohort for high-density specialist enrichment.

Modes:
- academic: modern science/academia/research-heavy people
- music: musician/singer/composer/conductor/songwriter/producer-heavy people

Preserves geographic/era/wiki-coverage diversity rather than taking only the most famous.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,re
from collections import defaultdict
from pathlib import Path

MUSIC=re.compile(r"musician|singer|composer|conductor|songwriter|rapper|disc jockey|record producer|guitarist|pianist|violinist|drummer",re.I)
ACADEMIC=re.compile(r"scientist|physicist|chemist|biologist|mathematician|professor|researcher|academic|engineer|astronomer|economist|computer scientist|physician",re.I)

def eligible(r,mode,min_birth):
    try:y=int(float(r.get("birth") or 0))
    except:return False
    if y<min_birth:return False
    text=" | ".join([r.get("level1_main_occ",""),r.get("level2_main_occ",""),r.get("level3_main_occ","")])
    if mode=="academic":
        return r.get("level1_main_occ")=="Discovery/Science" or bool(ACADEMIC.search(text))
    if mode=="music":
        return bool(MUSIC.search(text))
    return False

def tier(n):
    try:n=int(float(n or 0))
    except:n=0
    if n<=1:return "wiki1"
    if n<=3:return "wiki2-3"
    if n<=10:return "wiki4-10"
    return "wiki11+"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--mode",choices=["academic","music"],required=True)
    ap.add_argument("--target",type=int,default=5000)
    ap.add_argument("--min-birth",type=int,default=1900)
    ap.add_argument("--seed",type=int,default=20261003)
    args=ap.parse_args()
    with gzip.open(args.input,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=list(r.fieldnames or []);rows=[x for x in r if eligible(x,args.mode,args.min_birth)]
    rng=random.Random(args.seed);buckets=defaultdict(list)
    for x in rows:
        try:y=int(float(x.get("birth") or 0))
        except:y=0
        era=f"{(y//20)*20}-{(y//20)*20+19}"
        key=(x.get("un_region") or "unknown",era,tier(x.get("number_wiki_editions")),x.get("level3_main_occ") or "unknown")
        buckets[key].append(x)
    for xs in buckets.values():rng.shuffle(xs)
    keys=list(buckets);rng.shuffle(keys);chosen=[];used=set()
    while len(chosen)<args.target:
        progress=False
        for k in keys:
            if len(chosen)>=args.target:break
            while buckets[k]:
                x=buckets[k].pop();qid=x.get("wikidata_code") or x.get("wikidata_id")
                if not qid or qid in used:continue
                y=dict(x);y["specialist_mode"]=args.mode;y["specialist_stratum"]="|".join(k)
                chosen.append(y);used.add(qid);progress=True;break
        if not progress:break
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    outfields=fields+["specialist_mode","specialist_stratum"]
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=outfields);wr.writeheader();wr.writerows(chosen)
    report={"mode":args.mode,"eligible_population":len(rows),"target":args.target,"selected":len(chosen),
            "min_birth":args.min_birth,"represented_strata":len({x["specialist_stratum"] for x in chosen})}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
