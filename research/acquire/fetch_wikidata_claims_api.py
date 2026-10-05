"""Fetch dated Wikidata claims via wbgetentities for a known QID cohort.

This is the preferred route for a few thousand known people: the API returns claims in
batches and we parse temporal qualifiers locally, avoiding expensive SPARQL aggregation.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
PROPS={
 "P69":"education.affiliation",
 "P512":"education.degree",
 "P108":"career.employer",
 "P39":"career.position",
 "P106":"career.occupation",
 "P54":"career.team",
 "P410":"career.military_rank",
 "P551":"migration.residence",
 "P166":"recognition.award",
 "P463":"organization.member",
 "P1416":"organization.affiliation",
 "P102":"organization.party",
 "P26":"relationship.spouse"
}
TIME_QUALIFIERS={"P580":"start","P582":"end","P585":"point"}

def read_people(path:Path,ratings:set[str],id_column:str,rating_column:str|None):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or "").strip()
            rr=(r.get(rating_column) or "").strip() if rating_column else ""
            if q.startswith("Q") and (not ratings or rr in ratings):
                out[q]=rr
    return out

def get_entities(qids,retries=6):
    params={
      "action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
      "ids":"|".join(qids),"props":"claims"
    }
    body=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(API,data=body,headers={
          "User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r).get("entities",{})
        except urllib.error.HTTPError as e:
            retry=e.headers.get("Retry-After")
            delay=float(retry) if retry and retry.isdigit() else min(45,2**a+random.random())
            if e.code not in (429,500,502,503,504) or a==retries-1: raise
            time.sleep(delay)
        except Exception:
            if a==retries-1: raise
            time.sleep(min(45,2**a+random.random()))

def item_id_from_snak(snak):
    v=snak.get("datavalue",{}).get("value")
    return v.get("id") if isinstance(v,dict) and v.get("entity-type")=="item" else None

def time_values(claim,key):
    out=[]
    for snak in claim.get("qualifiers",{}).get(key,[]):
        v=snak.get("datavalue",{}).get("value")
        if isinstance(v,dict) and v.get("time"):
            out.append({
              "time":v.get("time"),"precision":v.get("precision"),
              "calendar_model":v.get("calendarmodel")
            })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--ratings",default="AA,A,B")
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--rating-column",default="rodden_rating")
    ap.add_argument("--batch-size",type=int,default=35)
    ap.add_argument("--sleep",type=float,default=.55)
    args=ap.parse_args()
    ratings={x for x in args.ratings.split(",") if x}
    rating_column=None if args.rating_column.lower() in {"","none","null"} else args.rating_column
    people=read_people(Path(args.input),ratings,args.id_column,rating_column)
    qids=sorted(people)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=[
      "person_id","rodden_rating","property","event_type","statement_id","value_qid","rank",
      "reference_count","start_json","end_json","point_json"
    ]
    rows=0; people_with=set(); failures=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for i in range(0,len(qids),args.batch_size):
            batch=qids[i:i+args.batch_size]
            try:
                entities=get_entities(batch)
            except Exception as e:
                failures+=len(batch)
                print(f"batch failed at {i}: {e!r}",flush=True)
                continue
            for q in batch:
                ent=entities.get(q,{})
                claims=ent.get("claims",{})
                for prop,event_type in PROPS.items():
                    for claim in claims.get(prop,[]):
                        value=item_id_from_snak(claim.get("mainsnak",{}))
                        if not value: continue
                        tv={name:time_values(claim,p) for p,name in TIME_QUALIFIERS.items()}
                        if not any(tv.values()): continue
                        wr.writerow({
                          "person_id":q,"rodden_rating":people[q],"property":prop,
                          "event_type":event_type,"statement_id":claim.get("id"),
                          "value_qid":value,"rank":claim.get("rank"),
                          "reference_count":len(claim.get("references",[])),
                          "start_json":json.dumps(tv["start"],separators=(",",":")),
                          "end_json":json.dumps(tv["end"],separators=(",",":")),
                          "point_json":json.dumps(tv["point"],separators=(",",":"))
                        })
                        rows+=1;people_with.add(q)
            if (i//args.batch_size+1)%10==0:
                print(f"people_done={min(i+args.batch_size,len(qids))}/{len(qids)} dated_claims={rows}",flush=True)
            w.flush();time.sleep(args.sleep)
    report={
      "input_people":len(qids),"people_with_dated_claims":len(people_with),
      "dated_claim_rows":rows,"batch_failures_people":failures,"properties":PROPS
    }
    rp=out.with_name(out.name[:-7]+".report.json" if out.name.endswith(".csv.gz") else out.stem+".report.json")
    rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
