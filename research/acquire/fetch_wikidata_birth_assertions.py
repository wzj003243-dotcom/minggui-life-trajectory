"""Fetch source-precision Wikidata P569 birth assertions for a BHHT cohort.

Input is bhht_core.csv.gz. Candidates are prioritized by BHHT visibility rank.
Wikidata time precision is preserved:
  9=year, 10=month, 11=day.
Only precision 11 is eligible for day-level BaZi features.

This script preserves competing P569 values instead of silently choosing one.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

def read_candidates(path: Path, limit: int):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for x in csv.DictReader(f):
            q=(x.get("wikidata_code") or "").strip()
            birth=(x.get("birth") or "").strip()
            if not q.startswith("Q") or not birth:
                continue
            try:
                rank=float(x.get("ranking_visib_5criteria") or 1e30)
            except Exception:
                rank=1e30
            rows.append((rank,q,birth))
    rows.sort(key=lambda x:(x[0],x[1]))
    return rows[:limit] if limit>0 else rows

def sparql_batch(qids, retries=6):
    values=" ".join("wd:"+q for q in qids)
    query=f"""SELECT ?person ?birth ?precision ?calendar ?rank (SAMPLE(?bp) AS ?birthplace) WHERE {{
      VALUES ?person {{ {values} }}
      ?person p:P569 ?statement .
      ?statement psv:P569 ?value ;
                 wikibase:rank ?rank .
      ?value wikibase:timeValue ?birth ;
             wikibase:timePrecision ?precision ;
             wikibase:timeCalendarModel ?calendar .
      FILTER(?rank != wikibase:DeprecatedRank)
      OPTIONAL {{ ?person wdt:P19 ?bp . }}
    }}
    GROUP BY ?person ?birth ?precision ?calendar ?rank"""
    data=urllib.parse.urlencode({"query":query,"format":"json"}).encode()
    req=urllib.request.Request(
        ENDPOINT,
        data=data,
        method="POST",
        headers={
            "User-Agent":UA,
            "Accept":"application/sparql-results+json",
            "Content-Type":"application/x-www-form-urlencoded",
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=90) as resp:
                return json.load(resp)["results"]["bindings"]
        except Exception:
            if attempt==retries-1:
                raise
            time.sleep(min(30,2**attempt)+random.random())
    return []

def entity_id(binding,key):
    value=binding.get(key,{}).get("value")
    if not value:
        return None
    tail=value.rsplit("/",1)[-1]
    return tail if tail.startswith("Q") else value

def birth_year_from_time(value):
    if not value:
        return None
    m=re.match(r"^([+-]?\d+)-",value)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bhht_core")
    ap.add_argument("output")
    ap.add_argument("--limit",type=int,default=25000)
    ap.add_argument("--batch-size",type=int,default=150)
    args=ap.parse_args()

    candidates=read_candidates(Path(args.bhht_core),args.limit)
    bhht_year={q:b for _,q,b in candidates}
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)

    fields=[
        "wikidata_id","birth_time_value","time_precision","calendar_model","statement_rank",
        "birthplace_qid","bhht_birth_year","birth_year_match"
    ]
    found=set()
    assertion_counts={}
    birth_values={}
    precision_assertions={9:0,10:0,11:0,"other":0}
    precision_people={9:set(),10:set(),11:set(),"other":set()}
    day_and_year_match=set()

    with gzip.open(out,"wt",encoding="utf-8",newline="") as fw:
        writer=csv.DictWriter(fw,fieldnames=fields)
        writer.writeheader()
        for start in range(0,len(candidates),args.batch_size):
            qids=[q for _,q,_ in candidates[start:start+args.batch_size]]
            bindings=sparql_batch(qids)
            for b in bindings:
                q=entity_id(b,"person")
                if not q:
                    continue
                birth=b.get("birth",{}).get("value")
                try:
                    precision=int(float(b.get("precision",{}).get("value")))
                except Exception:
                    precision=None
                bucket=precision if precision in (9,10,11) else "other"
                precision_assertions[bucket]+=1
                precision_people[bucket].add(q)
                found.add(q)
                assertion_counts[q]=assertion_counts.get(q,0)+1
                birth_values.setdefault(q,set()).add(birth)

                expected=bhht_year.get(q)
                actual=birth_year_from_time(birth)
                match=None
                try:
                    match=(actual==int(float(expected)))
                except Exception:
                    pass
                if precision==11 and match is True:
                    day_and_year_match.add(q)

                writer.writerow({
                    "wikidata_id":q,
                    "birth_time_value":birth,
                    "time_precision":precision,
                    "calendar_model":b.get("calendar",{}).get("value"),
                    "statement_rank":b.get("rank",{}).get("value"),
                    "birthplace_qid":entity_id(b,"birthplace"),
                    "bhht_birth_year":expected,
                    "birth_year_match":match,
                })
            batch_no=start//args.batch_size+1
            if batch_no%10==0:
                print(
                    f"batches={batch_no} people_done={min(start+args.batch_size,len(candidates))}/{len(candidates)} "
                    f"unique_found={len(found)} day_precision_people={len(precision_people[11])}",
                    flush=True,
                )
            time.sleep(.12)

    report={
        "requested_people":len(candidates),
        "unique_people_with_birth_assertion":len(found),
        "assertion_precision_counts":{str(k):v for k,v in precision_assertions.items()},
        "people_with_precision":{str(k):len(v) for k,v in precision_people.items()},
        "people_with_multiple_assertions":sum(v>1 for v in assertion_counts.values()),
        "people_with_conflicting_birth_values":sum(len(v)>1 for v in birth_values.values()),
        "people_with_day_precision":len(precision_people[11]),
        "people_with_day_precision_and_bhht_year_match":len(day_and_year_match),
        "day_precision_rate_over_requested":len(precision_people[11])/len(candidates) if candidates else 0,
        "day_precision_rate_over_found":len(precision_people[11])/len(found) if found else 0,
    }
    stem=out.name[:-7] if out.name.endswith(".csv.gz") else out.stem
    report_path=out.with_name(stem+".report.json")
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
