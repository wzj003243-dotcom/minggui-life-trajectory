"""Fetch source-precision Wikidata P569 birth assertions for a BHHT cohort.

Input is bhht_core.csv.gz. We prioritize the best-documented/notable rows only for an
initial materialized cohort, but the script scales by changing --limit.

Crucial: Wikidata timeValue alone is NOT enough. We store wikibase:timePrecision:
  9=year, 10=month, 11=day. Only precision 11 is eligible for day-level BaZi features.
"""
from __future__ import annotations
import argparse, csv, gzip, json, random, time, urllib.parse, urllib.request
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"

def read_candidates(path: Path, limit: int):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        for x in r:
            q=(x.get("wikidata_code") or "").strip()
            b=(x.get("birth") or "").strip()
            if not q.startswith("Q") or not b: continue
            try: rank=float(x.get("ranking_visib_5criteria") or 1e30)
            except: rank=1e30
            rows.append((rank,q,b))
    rows.sort(key=lambda x:(x[0],x[1]))
    if limit>0: rows=rows[:limit]
    return rows

def sparql_batch(qids, retries=6):
    values=" ".join("wd:"+q for q in qids)
    query=f"""SELECT ?person ?birth ?precision ?rank ?birthplace WHERE {{
      VALUES ?person {{ {values} }}
      ?person p:P569 ?statement .
      ?statement psv:P569 ?value ;
                 wikibase:rank ?rank .
      ?value wikibase:timeValue ?birth ;
             wikibase:timePrecision ?precision .
      OPTIONAL {{ ?person wdt:P19 ?birthplace . }}
    }}"""
    data=urllib.parse.urlencode({"query":query,"format":"json"}).encode()
    req=urllib.request.Request(
      ENDPOINT,data=data,method="POST",
      headers={
        "User-Agent":"MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)",
        "Accept":"application/sparql-results+json",
        "Content-Type":"application/x-www-form-urlencoded"
      }
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=90) as resp:
                return json.load(resp)["results"]["bindings"]
        except Exception:
            if attempt==retries-1: raise
            time.sleep(min(30,2**attempt)+random.random())
    return []

def clean_uri(v):
    if not v: return None
    x=v.get("value")
    if isinstance(x,str) and x.rsplit("/",1)[-1].startswith("Q"):
        return x.rsplit("/",1)[-1]
    return x

def year_from_wikidata_time(s):
    if not s: return None
    raw=s.lstrip("+").split("-",1)[0]
    try:return int(raw)
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bhht_core")
    ap.add_argument("output")
    ap.add_argument("--limit",type=int,default=25000)
    ap.add_argument("--batch-size",type=int,default=150)
    args=ap.parse_args()

    candidates=read_candidates(Path(args.bhht_core),args.limit)
    bhht_year={q:b for _,q,b in candidates}
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    fields=["wikidata_id","birth_time_value","time_precision","statement_rank","birthplace_qid","bhht_birth_year","birth_year_match"]
    found=set(); counts={9:0,10:0,11:0,"other":0}\n    precision_people={9:set(),10:set(),11:set(),"other":set()}\n    birth_values={}\n    with gzip.open(out,"wt",encoding="utf-8",newline="") as fw:
        w=csv.DictWriter(fw,fieldnames=fields); w.writeheader()
        for start in range(0,len(candidates),args.batch_size):
            qids=[q for _,q,_ in candidates[start:start+args.batch_size]]
            bindings=sparql_batch(qids)
            for b in bindings:
                q=clean_uri(b.get("person"))
                birth=b.get("birth",{}).get("value")
                try:p=int(float(b.get("precision",{}).get("value")))
                except:p=None
                if p in (9,10,11):\n                    counts[p]+=1; precision_people[p].add(q)\n                else:\n                    counts["other"]+=1; precision_people["other"].add(q)\n                expected=bhht_year.get(q)
                actual=year_from_wikidata_time(birth)
                match=None
                try: match=(actual==int(float(expected)))
                except: pass
                w.writerow({
                  "wikidata_id":q,
                  "birth_time_value":birth,
                  "time_precision":p,
                  "statement_rank":clean_uri(b.get("rank")),
                  "birthplace_qid":clean_uri(b.get("birthplace")),
                  "bhht_birth_year":expected,
                  "birth_year_match":match
                })
                found.add(q)\n                birth_values.setdefault(q,set()).add(birth)\n            if (start//args.batch_size+1)%10==0:
                print(f"batches={start//args.batch_size+1} people_done={min(start+args.batch_size,len(candidates))}/{len(candidates)} unique_found={len(found)} precision11={counts[11]}",flush=True)
            time.sleep(0.12)
    report={
      "requested_people":len(candidates),
      "unique_people_with_birth_assertion":len(found),
      "assertion_precision_counts":{str(k):v for k,v in counts.items()},\n      "people_with_precision":{str(k):len(v) for k,v in precision_people.items()},\n      "people_with_multiple_assertions":sum(len(v)>1 for v in birth_values.values()),\n      "people_with_conflicting_birth_values":sum(len(v)>1 for v in birth_values.values()),\n      "people_with_day_precision":len(precision_people[11]),\n      "day_precision_rate_over_requested":len(precision_people[11])/len(candidates) if candidates else 0,\n      "day_precision_rate_over_found":len(precision_people[11])/len(found) if found else 0\n    }
    stem=out.name[:-7] if out.name.endswith(".csv.gz") else out.stem\n    report_path=out.with_name(stem+".report.json")\n    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
