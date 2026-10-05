"""Select high-leverage timed-core people that have a verified external identifier bridge."""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import Counter
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("coverage");ap.add_argument("core");ap.add_argument("bridge");ap.add_argument("output")
    ap.add_argument("--target",type=int,default=250)
    ap.add_argument("--max-per-country",type=int,default=30)
    args=ap.parse_args()
    cov=json.load(open(args.coverage,encoding="utf-8"))
    by_id={x["person_id"]:x for x in cov.get("people",[])}
    eligible_ids=set()
    with gzip.open(args.bridge,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or "").strip()
            if q:eligible_ids.add(q)
    with gzip.open(args.core,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames or [];rows=list(r)

    cand=[]
    for row in rows:
        q=(row.get("wikidata_id") or "").strip()
        if q not in eligible_ids:continue
        c=by_id.get(q)
        if not c:continue
        e=int(c.get("effective_event_points") if c.get("effective_event_points") is not None else (c.get("event_count") or 0));d=int(c.get("domain_count") or 0);s=int(c.get("stage_count") or 0);src=int(c.get("source_family_count") or 0)
        # External-source requests are reserved for people still lacking a second source family.
        if src>=2:continue
        source_bonus=2.5
        score=4*min(e,15)/15+4*min(d,4)/4+3*min(s,3)/3+source_bonus
        if c.get("coverage_tier")=="bronze":score+=2
        if e>=10:score+=1
        if d>=3:score+=1
        country=(row.get("birth_country") or "unknown").strip() or "unknown"
        cand.append((score,q,country,row,c))
    cand.sort(key=lambda x:(-x[0],x[1]))
    selected=[];country_counts=Counter()
    for item in cand:
        if len(selected)>=args.target:break
        score,q,country,row,c=item
        if country_counts[country]>=args.max_per_country:continue
        selected.append(item);country_counts[country]+=1
    extra=["leverage_score","current_event_count","current_effective_event_points","current_domain_count","current_stage_count","current_source_family_count","current_coverage_tier"]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields+extra);wr.writeheader()
        for score,q,country,row,c in selected:
            x=dict(row);x.update({
              "leverage_score":round(score,6),"current_event_count":c.get("event_count",0),"current_effective_event_points":c.get("effective_event_points",c.get("event_count",0)),
              "current_domain_count":c.get("domain_count",0),"current_stage_count":c.get("stage_count",0),
              "current_source_family_count":c.get("source_family_count",0),
              "current_coverage_tier":c.get("coverage_tier","thin")
            });wr.writerow(x)
    report={
      "bridge_people":len(eligible_ids),"eligible_core_people":len(cand),"selected":len(selected),
      "target":args.target,"selected_tiers":dict(Counter(x[4].get("coverage_tier","thin") for x in selected)),
      "country_counts":dict(country_counts.most_common())
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
