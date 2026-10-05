"""Compare two LifeGraph coverage reports and quantify enrichment lift."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path

ORDER={"thin":0,"bronze":1,"silver":2,"gold":3}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("before");ap.add_argument("after");ap.add_argument("output")
    args=ap.parse_args()
    b=json.load(open(args.before,encoding="utf-8"))
    a=json.load(open(args.after,encoding="utf-8"))
    bp={x["person_id"]:x for x in b.get("people",[])}
    apm={x["person_id"]:x for x in a.get("people",[])}
    ids=sorted(set(bp)|set(apm))
    transitions=Counter();improved=[];regressed=[]
    for pid in ids:
        x=bp.get(pid,{})
        y=apm.get(pid,{})
        bt=x.get("coverage_tier","thin");at=y.get("coverage_tier","thin")
        transitions[f"{bt}->{at}"]+=1
        old_eff=x.get("effective_event_points",x.get("event_count",0)) or 0
        new_eff=y.get("effective_event_points",y.get("event_count",0)) or 0
        row={
          "person_id":pid,"before_tier":bt,"after_tier":at,
          "effective_points_delta":new_eff-old_eff,
          "domain_delta":(y.get("domain_count",0) or 0)-(x.get("domain_count",0) or 0),
          "stage_delta":(y.get("stage_count",0) or 0)-(x.get("stage_count",0) or 0),
          "source_family_delta":(y.get("source_family_count",0) or 0)-(x.get("source_family_count",0) or 0)
        }
        if ORDER.get(at,0)>ORDER.get(bt,0) or any(row[k]>0 for k in ("domain_delta","stage_delta","source_family_delta")):
            improved.append(row)
        if ORDER.get(at,0)<ORDER.get(bt,0):
            regressed.append(row)
    improved.sort(key=lambda x:(
      ORDER.get(x["after_tier"],0)-ORDER.get(x["before_tier"],0),
      x["source_family_delta"],x["domain_delta"],x["effective_points_delta"]
    ),reverse=True)
    summary={
      "people_compared":len(ids),
      "before_summary":b.get("summary",{}),
      "after_summary":a.get("summary",{}),
      "tier_transitions":dict(transitions),
      "people_with_any_coverage_gain":len(improved),
      "tier_upgrades":sum(ORDER.get(x["after_tier"],0)>ORDER.get(x["before_tier"],0) for x in improved),
      "regressions":len(regressed),
      "top_improvements":improved[:100]
    }
    Path(args.output).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "people_compared":summary["people_compared"],
      "tier_transitions":summary["tier_transitions"],
      "people_with_any_coverage_gain":summary["people_with_any_coverage_gain"],
      "tier_upgrades":summary["tier_upgrades"],
      "regressions":summary["regressions"]
    },ensure_ascii=False,indent=2))
if __name__=="__main__":main()
