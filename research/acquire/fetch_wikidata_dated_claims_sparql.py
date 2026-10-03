"""Fetch dated life-event claims for a known Wikidata cohort via batched WDQS VALUES queries.

This is substantially faster than wbgetentities when the only facts we need are claims with
P580/P582/P585 time qualifiers. Output schema matches fetch_wikidata_claims_api.py.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
UA="MingGuiLifeTrajectory/0.1 (https://github.com/wzj003243-dotcom/minggui-life-trajectory; public research)"
PROPS=[
 ("P69","education.affiliation"),("P108","career.employer"),("P39","career.position"),
 ("P551","migration.residence"),("P166","recognition.award"),("P463","organization.member"),
 ("P1416","organization.affiliation"),("P26","relationship.spouse")
]

def read_qids(path:Path,id_column:str):
    out=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or "").strip()
            if q.startswith("Q"):out.append(q)
    return list(dict.fromkeys(out))

def chunks(xs,n):
    for i in range(0,len(xs),n):yield xs[i:i+n]

def sparql(batch):
    values=" ".join("wd:"+q for q in batch)
    unions=[]
    for p,event in PROPS:
        unions.append(f'''{{ ?item p:{p} ?statement . ?statement ps:{p} ?value . BIND("{p}" AS ?property) BIND("{event}" AS ?eventType) }}''')
    return f'''
SELECT ?item ?property ?eventType ?statement ?value ?rank
       ?start ?startPrecision ?startCalendar
       ?end ?endPrecision ?endCalendar
       ?point ?pointPrecision ?pointCalendar WHERE {{
  VALUES ?item {{ {values} }}
  {" UNION ".join(unions)}
  ?statement wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  OPTIONAL {{
    ?statement pqv:P580 ?startNode .
    ?startNode wikibase:timeValue ?start ; wikibase:timePrecision ?startPrecision .
    OPTIONAL {{ ?startNode wikibase:timeCalendarModel ?startCalendar . }}
  }}
  OPTIONAL {{
    ?statement pqv:P582 ?endNode .
    ?endNode wikibase:timeValue ?end ; wikibase:timePrecision ?endPrecision .
    OPTIONAL {{ ?endNode wikibase:timeCalendarModel ?endCalendar . }}
  }}
  OPTIONAL {{
    ?statement pqv:P585 ?pointNode .
    ?pointNode wikibase:timeValue ?point ; wikibase:timePrecision ?pointPrecision .
    OPTIONAL {{ ?pointNode wikibase:timeCalendarModel ?pointCalendar . }}
  }}
  FILTER(BOUND(?start) || BOUND(?end) || BOUND(?point))
}}
'''

def query(batch,retries=3):
    body=urllib.parse.urlencode({"query":sparql(batch),"format":"json"}).encode()
    for a in range(retries):
        req=urllib.request.Request(ENDPOINT,data=body,headers={
          "User-Agent":UA,"Accept":"application/sparql-results+json",
          "Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=75) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or a==retries-1:raise
            retry=e.headers.get("Retry-After")
            delay=float(retry) if retry and retry.isdigit() else min(12,2**a+random.random())
            time.sleep(delay)
        except Exception:
            if a==retries-1:raise
            time.sleep(min(12,2**a+random.random()))

def safe_query(batch, depth=0):
    try:
        return query(batch), []
    except Exception as e:
        if len(batch) <= 10:
            return [], [(q, repr(e)) for q in batch]
        mid=len(batch)//2
        left,lf=safe_query(batch[:mid],depth+1)
        right,rf=safe_query(batch[mid:],depth+1)
        return left+right, lf+rf

def qid(uri):return uri.rsplit("/",1)[-1]
def rank(uri):return uri.rsplit("#",1)[-1].replace("Rank","").lower()
def time_obj(b,prefix):
    if prefix not in b:return None
    return {
      "time":b[prefix]["value"],
      "precision":int(b.get(prefix+"Precision",{}).get("value") or 0),
      "calendar_model":b.get(prefix+"Calendar",{}).get("value")
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--batch-size",type=int,default=80)
    ap.add_argument("--sleep",type=float,default=.25)
    args=ap.parse_args()
    qids=read_qids(Path(args.input),args.id_column)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["person_id","rodden_rating","property","event_type","statement_id","value_qid","rank",
            "reference_count","start_json","end_json","point_json"]
    rows=0;people=set();failed=0;failed_examples=[]
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for bi,batch in enumerate(chunks(qids,args.batch_size),1):
            bindings, failures=safe_query(batch)
            if failures:
                failed+=len(failures)
                failed_examples.extend(failures[:max(0,25-len(failed_examples))])
                print(f"batch_partial_failure={bi} failed_people={len(failures)}",flush=True)
            grouped={}
            for b in bindings:
                sid=b["statement"]["value"]
                key=(qid(b["item"]["value"]),sid)
                g=grouped.setdefault(key,{
                  "person_id":key[0],"property":b["property"]["value"],"event_type":b["eventType"]["value"],
                  "statement_id":sid,"value_qid":qid(b["value"]["value"]),"rank":rank(b["rank"]["value"]),
                  "start":[],"end":[],"point":[]
                })
                for name in ("start","end","point"):
                    obj=time_obj(b,name)
                    if obj and obj not in g[name]:g[name].append(obj)
            for g in grouped.values():
                wr.writerow({
                  "person_id":g["person_id"],"rodden_rating":"","property":g["property"],"event_type":g["event_type"],
                  "statement_id":g["statement_id"],"value_qid":g["value_qid"],"rank":g["rank"],
                  "reference_count":0,
                  "start_json":json.dumps(g["start"],separators=(",",":")),
                  "end_json":json.dumps(g["end"],separators=(",",":")),
                  "point_json":json.dumps(g["point"],separators=(",",":"))
                });rows+=1;people.add(g["person_id"])
            if bi%10==0:print(f"batches={bi} people_done={min(bi*args.batch_size,len(qids))}/{len(qids)} claims={rows}",flush=True)
            w.flush();time.sleep(args.sleep)
    report={"input_people":len(qids),"people_with_dated_claims":len(people),"dated_claim_rows":rows,
            "failed_people":failed,"failed_examples":failed_examples,"batch_size":args.batch_size,
            "transport":"WDQS_VALUES_ADAPTIVE_SPLIT"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
