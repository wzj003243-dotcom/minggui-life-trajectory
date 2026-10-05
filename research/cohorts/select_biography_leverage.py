"""Select high-leverage timed-core people for biography enrichment.

Goal: spend expensive revision-text extraction on people most likely to cross the LifeGraph
Silver/Gold thresholds after gaining an independent source and additional event domains.

Inputs:
  core_lifegraph_coverage.json
  timed_linked_cohort.csv.gz
Output:
  biography_leverage_<N>.csv.gz
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from collections import defaultdict,Counter
from pathlib import Path

def year_from_birth(row):
    raw=(row.get("birth_date_normalized") or row.get("birth_date_source") or "")
    try:return int(raw[:4])
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("coverage");ap.add_argument("core");ap.add_argument("output")
    ap.add_argument("--target",type=int,default=300)
    ap.add_argument("--max-per-country",type=int,default=30)
    args=ap.parse_args()

    cov=json.load(open(args.coverage,encoding="utf-8"))
    by_id={x["person_id"]:x for x in cov.get("people",[])}
    with gzip.open(args.core,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f);fields=r.fieldnames or [];core=list(r)

    candidates=[]
    for row in core:
        q=(row.get("wikidata_id") or "").strip()
        c=by_id.get(q)
        if not c:continue
        if not (row.get("wikipedia_url") or "").strip():continue
        # Biography's highest value is adding a second independent source.
        if int(c.get("source_family_count") or 0)>=2:continue
        e=int(c.get("event_count") or 0);d=int(c.get("domain_count") or 0);s=int(c.get("stage_count") or 0)
        # Prefer people already partially observed, but do not waste extraction on already-saturated rows.
        if e<3:continue
        event_closeness=min(e,15)/15
        domain_closeness=min(d,4)/4
        stage_closeness=min(s,3)/3
        bronze_bonus=2.0 if c.get("coverage_tier")=="bronze" else 0.0
        near_silver_bonus=(1.0 if e>=10 else 0)+(1.0 if d>=3 else 0)+(1.0 if s>=3 else 0)
        # Slight priority to people not already overwhelmed by hundreds of atomic records.
        saturation_penalty=max(0,e-30)*0.02
        score=4*event_closeness+4*domain_closeness+3*stage_closeness+bronze_bonus+near_silver_bonus-saturation_penalty
        y=year_from_birth(row);decade=(y//10*10 if y else None)
        country=(row.get("birth_country") or "unknown").strip() or "unknown"
        gender=(row.get("gender") or "unknown").strip() or "unknown"
        candidates.append((score,q,country,gender,decade,row,c))

    # Diversity-aware greedy selection. Country cap prevents one famous-person ecosystem dominating.
    candidates.sort(key=lambda x:(-x[0],x[1]))
    selected=[];country_count=Counter();strata_count=Counter()
    remaining=candidates[:]
    while remaining and len(selected)<args.target:
        best_idx=None;best_value=None
        for i,item in enumerate(remaining[:max(1000,args.target*5)]):
            score,q,country,gender,decade,row,c=item
            if country_count[country]>=args.max_per_country:continue
            stratum=(country,gender,decade)
            # Reward underrepresented strata while preserving leverage score.
            value=score-0.15*strata_count[stratum]-0.03*country_count[country]
            if best_value is None or value>best_value:
                best_value=value;best_idx=i
        if best_idx is None:break
        item=remaining.pop(best_idx)
        score,q,country,gender,decade,row,c=item
        selected.append(item);country_count[country]+=1;strata_count[(country,gender,decade)]+=1

    extra=[
      "leverage_score","current_event_count","current_domain_count","current_stage_count",
      "current_source_family_count","current_coverage_tier","birth_decade"
    ]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields+extra);wr.writeheader()
        for score,q,country,gender,decade,row,c in selected:
            x=dict(row);x.update({
              "leverage_score":round(score,6),"current_event_count":c.get("event_count",0),
              "current_domain_count":c.get("domain_count",0),"current_stage_count":c.get("stage_count",0),
              "current_source_family_count":c.get("source_family_count",0),
              "current_coverage_tier":c.get("coverage_tier","thin"),"birth_decade":decade or ""
            });wr.writerow(x)

    report={
      "eligible":len(candidates),"selected":len(selected),"target":args.target,
      "selection_goal":"maximize likely Silver/Gold conversions while adding Wikipedia as independent source",
      "selected_current_tiers":dict(Counter(x[6].get("coverage_tier","thin") for x in selected)),
      "selected_country_counts":dict(country_count.most_common()),
      "median_current_events":(sorted(x[6].get("event_count",0) for x in selected)[len(selected)//2] if selected else 0)
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
