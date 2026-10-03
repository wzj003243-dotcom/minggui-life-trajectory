"""Convert OpenAlex scholarly work events into yearly academic state vectors.

No citation totals are used: current citation counts would leak future information at historical
cutoffs. States are based on publication-time facts only.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path

def entropy(counter):
    n=sum(counter.values())
    if not n:return 0.0
    return -sum((v/n)*math.log(v/n) for v in counter.values() if v)

def splitpipe(v):return [x for x in (v or "").split("|") if x]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("events");ap.add_argument("output");args=ap.parse_args()
    by=defaultdict(list)
    with gzip.open(args.events,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            try:y=int((r.get("event_date") or "")[:4])
            except:continue
            by[r["person_id"]].append((y,r))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=[
      "person_id","year","works_count","first_author_count","corresponding_count",
      "unique_institutions","unique_institution_countries","unique_fields","field_entropy",
      "dominant_field_id","dominant_field_name","dominant_institution_id",
      "field_switch","institution_switch","rolling_3y_works",
      "cumulative_works","cumulative_unique_fields","cumulative_unique_institutions"
    ]
    rows=0;people=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,items in by.items():
            people+=1
            years=sorted({y for y,_ in items})
            yearly=defaultdict(list)
            for y,r in items:yearly[y].append(r)
            cumworks=0;cumfields=set();cuminst=set();prev_field=None;prev_inst=None
            hist_counts={}
            for y in range(min(years),max(years)+1):
                evs=yearly.get(y,[])
                works=len(evs);cumworks+=works
                fc=Counter((e.get("primary_field_id") or "unknown") for e in evs)
                fname={}
                inst=Counter();countries=set()
                first=corresp=0
                for e in evs:
                    fid=e.get("primary_field_id") or "unknown"
                    if e.get("primary_field_name"):fname[fid]=e["primary_field_name"]
                    for x in splitpipe(e.get("institution_ids")):inst[x]+=1;cuminst.add(x)
                    countries.update(splitpipe(e.get("institution_countries")))
                    if (e.get("author_position") or "")=="first":first+=1
                    if str(e.get("is_corresponding") or "").lower()=="true":corresp+=1
                    if fid!="unknown":cumfields.add(fid)
                dom_field=fc.most_common(1)[0][0] if fc else ""
                dom_inst=inst.most_common(1)[0][0] if inst else ""
                field_switch=int(bool(prev_field and dom_field and dom_field!=prev_field))
                inst_switch=int(bool(prev_inst and dom_inst and dom_inst!=prev_inst))
                if dom_field:prev_field=dom_field
                if dom_inst:prev_inst=dom_inst
                hist_counts[y]=works
                rolling=sum(hist_counts.get(k,0) for k in (y-2,y-1,y))
                wr.writerow({
                  "person_id":pid,"year":y,"works_count":works,"first_author_count":first,
                  "corresponding_count":corresp,"unique_institutions":len(inst),
                  "unique_institution_countries":len(countries),"unique_fields":len([k for k in fc if k!="unknown"]),
                  "field_entropy":round(entropy(Counter({k:v for k,v in fc.items() if k!="unknown"})),6),
                  "dominant_field_id":dom_field,"dominant_field_name":fname.get(dom_field,""),
                  "dominant_institution_id":dom_inst,"field_switch":field_switch,
                  "institution_switch":inst_switch,"rolling_3y_works":rolling,
                  "cumulative_works":cumworks,"cumulative_unique_fields":len(cumfields),
                  "cumulative_unique_institutions":len(cuminst)
                });rows+=1
    report={
      "people":people,"year_state_rows":rows,
      "features":"publication-time only; no current citation totals",
      "meaning":"annual academic life state suitable for cutoff-safe trajectory models"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
