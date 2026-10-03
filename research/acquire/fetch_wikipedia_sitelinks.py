"""Resolve Wikidata QIDs to preferred enwiki/zhwiki titles via WDQS in bulk."""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
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

def query_batch(qids,retries=7):
    if not qids:return []
    values=" ".join("wd:"+q for q in qids)
    query=f"""SELECT ?person ?article ?site WHERE {{
      VALUES ?person {{ {values} }}
      VALUES ?site {{ <https://en.wikipedia.org/> <https://zh.wikipedia.org/> }}
      ?article schema:about ?person ;
               schema:isPartOf ?site .
    }}"""
    body=urllib.parse.urlencode({"query":query,"format":"json"}).encode()
    for a in range(retries):
        req=urllib.request.Request(ENDPOINT,data=body,headers={
          "User-Agent":UA,"Accept":"application/sparql-results+json",
          "Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if len(qids)>1 and (e.code==400 or a==retries-1):
                m=len(qids)//2
                return query_batch(qids[:m],retries)+query_batch(qids[m:],retries)
            if e.code not in (429,500,502,503,504):raise
            retry=e.headers.get("Retry-After")
            try:d=float(retry) if retry else min(60,max(3,2**a))+random.random()
            except:d=min(60,max(3,2**a))+random.random()
            time.sleep(d)
        except Exception:
            if a==retries-1:
                if len(qids)>1:
                    m=len(qids)//2
                    return query_batch(qids[:m],retries)+query_batch(qids[m:],retries)
                return []
            time.sleep(min(45,max(2,2**a))+random.random())
    return []

def main():
    ap=argparse.ArgumentParser();ap.add_argument("cohort");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--limit",type=int,default=0)
    ap.add_argument("--batch-size",type=int,default=100);args=ap.parse_args()
    qids=read_qids(Path(args.cohort),args.id_column,args.limit);found=defaultdict(dict)
    for i in range(0,len(qids),args.batch_size):
        batch=qids[i:i+args.batch_size]
        for b in query_batch(batch):
            q=b["person"]["value"].rsplit("/",1)[-1];siteurl=b["site"]["value"];article=b["article"]["value"]
            site="enwiki" if "en.wikipedia.org" in siteurl else "zhwiki"
            try:title=urllib.parse.unquote(urllib.parse.urlparse(article).path.split("/wiki/",1)[1]).replace("_"," ")
            except:continue
            found[q][site]=title
        if (i//args.batch_size+1)%5==0:
            print(f"qid={min(i+args.batch_size,len(qids))}/{len(qids)} resolved={len(found)}",flush=True)
        time.sleep(.15)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=["wikidata_id","site","title"]);wr.writeheader()
        for q in qids:
            d=found.get(q,{})
            if d.get("enwiki"):wr.writerow({"wikidata_id":q,"site":"enwiki","title":d["enwiki"]})
            elif d.get("zhwiki"):wr.writerow({"wikidata_id":q,"site":"zhwiki","title":d["zhwiki"]})
    report={"input_qids":len(qids),"resolved_people":len(found),"coverage":len(found)/len(qids) if qids else 0}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
