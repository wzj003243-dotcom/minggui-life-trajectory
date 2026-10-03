"""Fetch time-qualified Wikidata life statements for a resolved person cohort.

Input may be adb_wikidata_links.csv.gz or any CSV/GZ with a wikidata_id column.
The output is source-backed structured event candidates, not a biography summary.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

PROPS={
 "P69":"education.affiliation",
 "P108":"career.employer",
 "P39":"career.position",
 "P551":"migration.residence",
 "P166":"recognition.award",
 "P463":"organization.member",
 "P1416":"organization.affiliation",
 "P26":"relationship.spouse"
}

def read_qids(path:Path, ratings=None):
    opener=gzip.open if path.suffix==".gz" else open
    out=[]
    with opener(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or "").strip()
            rr=(r.get("rodden_rating") or "").strip()
            if q.startswith("Q") and (not ratings or rr in ratings): out.append(q)
    return sorted(set(out))

def query_batch(qids,retries=6):
    values=" ".join("wd:"+q for q in qids)
    arms=[]
    for p in PROPS:
        arms.append(f'{{ BIND("{p}" AS ?property) ?person p:{p} ?statement . ?statement ps:{p} ?value . }}')
    unions=" UNION ".join(arms)
    query=f"""SELECT ?person ?property ?value ?start ?end ?point ?rank (COUNT(DISTINCT ?ref) AS ?refs) WHERE {{
      VALUES ?person {{ {values} }}
      {unions}
      ?statement wikibase:rank ?rank .
      OPTIONAL {{ ?statement pq:P580 ?start . }}
      OPTIONAL {{ ?statement pq:P582 ?end . }}
      OPTIONAL {{ ?statement pq:P585 ?point . }}
      OPTIONAL {{ ?statement prov:wasDerivedFrom ?ref . }}\n      FILTER(BOUND(?start) || BOUND(?end) || BOUND(?point))\n    }}
    GROUP BY ?person ?property ?value ?start ?end ?point ?rank"""
    data=urllib.parse.urlencode({"query":query,"format":"json"}).encode()
    req=urllib.request.Request(ENDPOINT,data=data,method="POST",headers={
      "User-Agent":UA,"Accept":"application/sparql-results+json",
      "Content-Type":"application/x-www-form-urlencoded"
    })
    for a in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except Exception:
            if a==retries-1: raise
            time.sleep(min(30,2**a)+random.random())

def qid(binding,key):
    v=binding.get(key,{}).get("value")
    return v.rsplit("/",1)[-1] if isinstance(v,str) and "/entity/Q" in v else v

def val(binding,key):
    return binding.get(key,{}).get("value")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--ratings",default="AA,A,B",help="comma-separated; blank means all")
    ap.add_argument("--batch-size",type=int,default=75)
    args=ap.parse_args()
    ratings={x for x in args.ratings.split(",") if x}
    people=read_qids(Path(args.input),ratings)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["person_id","property","event_type","value_qid","start","end","point","statement_rank","reference_count"]
    rows=0;people_with=set()
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for i in range(0,len(people),args.batch_size):
            batch=people[i:i+args.batch_size]
            for b in query_batch(batch):
                person=qid(b,"person"); prop=val(b,"property")
                wr.writerow({
                  "person_id":person,"property":prop,"event_type":PROPS.get(prop),
                  "value_qid":qid(b,"value"),"start":val(b,"start"),"end":val(b,"end"),
                  "point":val(b,"point"),"statement_rank":val(b,"rank"),
                  "reference_count":int(float(val(b,"refs") or 0))
                })
                rows+=1;people_with.add(person)
            if (i//args.batch_size+1)%10==0:
                print(f"people_done={min(i+args.batch_size,len(people))}/{len(people)} statements={rows}",flush=True)
            time.sleep(.12)
    report={"input_people":len(people),"people_with_statements":len(people_with),"statement_rows":rows,"properties":PROPS}
    out.with_name(out.name[:-7]+".report.json" if out.name.endswith(".csv.gz") else out.stem+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
