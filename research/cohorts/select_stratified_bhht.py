"""Build a deterministic, balanced exact-date enrichment cohort from BHHT.

The full BHHT table remains the reality baseline. This selector creates a day-level cohort
for metaphysics experiments without simply taking the globally most famous people.

Strata:
  region × level1 occupation × birth era × Wikipedia-edition tier

Sampling is deterministic by QID hash within stratum. A sampling_weight is emitted so
population-like evaluations can reweight the balanced sample back toward BHHT.

Default scope: 1800-2005, non_missing_score >= 2.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,heapq,json,math
from collections import Counter,defaultdict
from pathlib import Path

ERAS=[
  (1800,1849,"1800-1849"),(1850,1899,"1850-1899"),(1900,1924,"1900-1924"),
  (1925,1949,"1925-1949"),(1950,1969,"1950-1969"),(1970,1989,"1970-1989"),
  (1990,2005,"1990-2005")
]

def era(y):
    for lo,hi,label in ERAS:
        if lo<=y<=hi:return label
    return None

def tier(n):
    if n<=1:return "wiki1"
    if n<=3:return "wiki2-3"
    if n<=10:return "wiki4-10"
    return "wiki11+"

def parse(row,min_score):
    q=(row.get("wikidata_code") or "").strip()
    if not q.startswith("Q"):return None
    try:y=int(float(row.get("birth") or "nan"))
    except:return None
    e=era(y)
    if not e:return None
    try:score=int(float(row.get("non_missing_score") or 0))
    except:score=0
    if score<min_score:return None
    region=(row.get("un_region") or "Missing").strip() or "Missing"
    occ=(row.get("level1_main_occ") or "Missing").strip() or "Missing"
    try:ned=int(float(row.get("number_wiki_editions") or 0))
    except:ned=0
    s=(region,occ,e,tier(ned))
    return q,y,s,ned,score

def openr(path):
    return gzip.open(path,"rt",encoding="utf-8",newline="") if str(path).endswith(".gz") else open(path,"r",encoding="utf-8",newline="")

def allocate(counts,target,min_per):
    keys=list(counts)
    if not keys:return {}
    base={k:min(counts[k],min_per) for k in keys}
    remaining=max(0,target-sum(base.values()))
    weights={k:math.sqrt(max(0,counts[k]-base[k])) for k in keys}
    total=sum(weights.values()) or 1
    quotas=dict(base)
    fractions=[]
    for k in keys:
        room=max(0,counts[k]-quotas[k])
        raw=remaining*weights[k]/total
        add=min(room,int(raw))
        quotas[k]+=add
        fractions.append((raw-int(raw),k))
    left=min(target-sum(quotas.values()),sum(counts[k]-quotas[k] for k in keys))
    for _,k in sorted(fractions,reverse=True):
        if left<=0:break
        if quotas[k]<counts[k]:
            quotas[k]+=1;left-=1
    # If rounding / caps still leave room, cycle by remaining capacity.
    while left>0:
        moved=0
        for k in sorted(keys,key=lambda x:counts[x]-quotas[x],reverse=True):
            if quotas[k]<counts[k]:
                quotas[k]+=1;left-=1;moved+=1
                if left<=0:break
        if not moved:break
    return quotas

def priority(qid):
    return int.from_bytes(hashlib.sha256(qid.encode()).digest()[:8],"big")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--target",type=int,default=100000)
    ap.add_argument("--min-per-stratum",type=int,default=20)
    ap.add_argument("--min-score",type=int,default=2)
    args=ap.parse_args()
    src=Path(args.input);out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)

    counts=Counter()
    with openr(src) as f:
        for row in csv.DictReader(f):
            p=parse(row,args.min_score)
            if p:counts[p[2]]+=1
    quotas=allocate(counts,args.target,args.min_per_stratum)

    # max-heaps using negative deterministic priority, keeping smallest hashes.
    heaps=defaultdict(list)
    keep_fields=None
    with openr(src) as f:
        r=csv.DictReader(f);keep_fields=r.fieldnames
        for row in r:
            p=parse(row,args.min_score)
            if not p:continue
            q,y,s,ned,score=p;quota=quotas.get(s,0)
            if quota<=0:continue
            pri=priority(q)
            item=(-pri,q,row)
            h=heaps[s]
            if len(h)<quota:heapq.heappush(h,item)
            elif pri < -h[0][0]:heapq.heapreplace(h,item)

    fields=(keep_fields or [])+["sample_stratum","stratum_population","stratum_sample","sampling_weight"]
    n=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for s,h in sorted(heaps.items()):
            sample_n=len(h);pop=counts[s];weight=pop/sample_n if sample_n else None
            for _,q,row in sorted(h,key=lambda x:x[1]):
                x=dict(row)
                x.update({"sample_stratum":"|".join(s),"stratum_population":pop,"stratum_sample":sample_n,"sampling_weight":weight})
                wr.writerow(x);n+=1
    report={
      "target":args.target,"selected":n,"eligible_population":sum(counts.values()),
      "nonempty_strata":len(counts),"sampled_strata":len(heaps),
      "year_scope":[1800,2005],"min_non_missing_score":args.min_score,
      "stratum_dimensions":["un_region","level1_main_occ","birth_era","wikipedia_edition_tier"]
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
