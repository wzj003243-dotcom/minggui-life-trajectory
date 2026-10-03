"""Select a stable stratified subset of clean exact-date people for expensive life-event enrichment."""
from __future__ import annotations
import argparse,csv,gzip,json,hashlib
from collections import defaultdict
from pathlib import Path

def stable_key(qid:str)->str:
    return hashlib.sha256(qid.encode()).hexdigest()

def load_canonical(path:Path):
    ok=set()
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("canonical_status") in ("canonical_unique","canonical_preferred") and r.get("birth_date"):
                ok.add(r["wikidata_id"])
    return ok

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bhht_sample")
    ap.add_argument("canonical_births")
    ap.add_argument("output")
    ap.add_argument("--target",type=int,default=8000)
    args=ap.parse_args()

    eligible=load_canonical(Path(args.canonical_births))
    strata=defaultdict(list)
    fields=None
    with gzip.open(args.bhht_sample,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames
        for row in r:
            q=(row.get("wikidata_code") or "").strip()
            if q not in eligible: continue
            strata[row.get("sample_stratum") or "unknown"].append(row)

    total=sum(map(len,strata.values()))
    if not total: raise SystemExit("no eligible rows")
    # Proportional allocation with at least one per non-empty stratum, then deterministic fill.
    alloc={}
    used=0
    for s,rows in strata.items():
        n=max(1,round(args.target*len(rows)/total))
        n=min(n,len(rows))
        alloc[s]=n;used+=n
    # Trim or fill to exact target using deterministic global ordering.
    selected=[]
    for s,rows in strata.items():
        rows=sorted(rows,key=lambda x:stable_key(x["wikidata_code"]))
        selected.extend(rows[:alloc[s]])
    selected=sorted(selected,key=lambda x:stable_key(x["wikidata_code"]))
    if len(selected)>args.target:
        selected=selected[:args.target]
    elif len(selected)<args.target:
        chosen={r["wikidata_code"] for r in selected}
        pool=[]
        for rows in strata.values():
            for r in rows:
                if r["wikidata_code"] not in chosen: pool.append(r)
        pool=sorted(pool,key=lambda x:stable_key(x["wikidata_code"]))
        selected.extend(pool[:args.target-len(selected)])

    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out_fields=["wikidata_id","sample_stratum","birth","gender","level1_main_occ","level2_main_occ",
                "level3_main_occ","un_region","un_subregion","number_wiki_editions","sampling_weight"]
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=out_fields);wr.writeheader()
        for r in selected:
            wr.writerow({
              "wikidata_id":r["wikidata_code"],
              "sample_stratum":r.get("sample_stratum"),
              "birth":r.get("birth"),"gender":r.get("gender"),
              "level1_main_occ":r.get("level1_main_occ"),"level2_main_occ":r.get("level2_main_occ"),
              "level3_main_occ":r.get("level3_main_occ"),"un_region":r.get("un_region"),
              "un_subregion":r.get("un_subregion"),"number_wiki_editions":r.get("number_wiki_editions"),
              "sampling_weight":r.get("sampling_weight")
            })
    report={"target":args.target,"selected":len(selected),"eligible_exact_date_population":total,
            "strata_with_selected":len({r.get("sample_stratum") for r in selected})}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
