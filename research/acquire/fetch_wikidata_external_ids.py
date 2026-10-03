"""Fetch simple Wikidata external-id mappings for a known QID cohort via WDQS.

Use this for lightweight identity properties such as:
  P496 ORCID
  P434 MusicBrainz artist ID

The output preserves all values; downstream pipelines require exactly one accepted ID when
identity ambiguity matters.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
UA="MingGuiLifeTrajectory/0.1 (https://github.com/wzj003243-dotcom/minggui-life-trajectory; research)"

def read_qids(path,id_column,limit):
    out=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or r.get("wikidata_id") or r.get("wikidata_code") or "").strip()
            if q.startswith("Q") and q[1:].isdigit():out.append(q)
    out=sorted(set(out),key=lambda x:int(x[1:]))
    return out[:limit] if limit>0 else out

def query_batch(qids,prop,retries=7):
    if not qids:return []
    values=" ".join("wd:"+q for q in qids)
    sparql=f"""SELECT ?person ?external WHERE {{
      VALUES ?person {{ {values} }}
      ?person wdt:{prop} ?external .
    }}"""
    body=urllib.parse.urlencode({"query":sparql,"format":"json"}).encode()
    for a in range(retries):
        req=urllib.request.Request(ENDPOINT,data=body,headers={
          "User-Agent":UA,"Accept":"application/sparql-results+json",
          "Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code==400 and len(qids)>1:
                mid=len(qids)//2
                return query_batch(qids[:mid],prop,retries)+query_batch(qids[mid:],prop,retries)
            if e.code not in (429,500,502,503,504) or a==retries-1:
                if len(qids)>1:
                    mid=len(qids)//2
                    return query_batch(qids[:mid],prop,retries)+query_batch(qids[mid:],prop,retries)
                raise
            retry=e.headers.get("Retry-After")
            try:delay=float(retry) if retry else min(60,max(3,2**a))+random.random()
            except:delay=min(60,max(3,2**a))+random.random()
            time.sleep(delay)
        except Exception:
            if a==retries-1:
                if len(qids)>1:
                    mid=len(qids)//2
                    return query_batch(qids[:mid],prop,retries)+query_batch(qids[mid:],prop,retries)
                raise
            time.sleep(min(45,max(2,2**a))+random.random())
    return []

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cohort");ap.add_argument("output")
    ap.add_argument("--property",required=True)
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--limit",type=int,default=0)
    ap.add_argument("--batch-size",type=int,default=120)
    ap.add_argument("--sleep",type=float,default=.25)
    args=ap.parse_args()
    qids=read_qids(Path(args.cohort),args.id_column,args.limit)
    rows=[];failed=0
    for i in range(0,len(qids),args.batch_size):
        batch=qids[i:i+args.batch_size]
        try:
            got=query_batch(batch,args.property)
        except Exception as e:
            failed+=len(batch);print(f"warning: external-id batch failed {i}: {e!r}",flush=True);continue
        for b in got:
            q=b["person"]["value"].rsplit("/",1)[-1]
            rows.append((q,b["external"]["value"]))
        if (i//args.batch_size+1)%10==0:
            print(f"qid_done={min(i+args.batch_size,len(qids))}/{len(qids)} mapped_rows={len(rows)}",flush=True)
        time.sleep(args.sleep)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=["wikidata_id","property","external_id"]);wr.writeheader()
        for q,v in rows:wr.writerow({"wikidata_id":q,"property":args.property,"external_id":v})
    people=len({q for q,_ in rows})
    report={"input_qids":len(qids),"property":args.property,"mapping_rows":len(rows),
            "people_with_external_id":people,"coverage":people/len(qids) if qids else 0,
            "failed_qids":failed}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
