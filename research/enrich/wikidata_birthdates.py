"""Batch-enrich a QID cohort with precise Wikidata P569 statements.

Uses WDQS only for a bounded selected cohort, not for the full 2.29M BHHT database.
Preserves precision/rank and all non-deprecated competing birth statements.

Example:
  python research/enrich/wikidata_birthdates.py cohort.csv.gz birth_assertions.ndjson
"""
from __future__ import annotations
import csv,gzip,json,sys,time,urllib.parse,urllib.request
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
USER_AGENT="MingGuiLifeTrajectory/0.1 (https://github.com/wzj003243-dotcom/minggui-life-trajectory; research)"
BATCH=150

def read_qids(path:Path):
    opener=gzip.open if path.suffix==".gz" else open
    with opener(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            q=row.get("wikidata_code") or row.get("qid") or ""
            if q.startswith("Q"): yield q

def chunks(xs,n):
    x=[]
    for item in xs:
        x.append(item)
        if len(x)>=n:
            yield x;x=[]
    if x: yield x

def query(batch,retries=5):
    values=" ".join("wd:"+q for q in batch)
    sparql=f"""
SELECT ?item ?time ?precision ?rank WHERE {{
  VALUES ?item {{ {values} }}
  ?item p:P569 ?statement .
  ?statement psv:P569 ?value ;
             wikibase:rank ?rank .
  ?value wikibase:timeValue ?time ;
         wikibase:timePrecision ?precision .
  FILTER(?rank != wikibase:DeprecatedRank)
}}
"""
    body=urllib.parse.urlencode({"query":sparql,"format":"json"}).encode()
    for attempt in range(retries):
        req=urllib.request.Request(ENDPOINT,data=body,headers={
          "User-Agent":USER_AGENT,
          "Accept":"application/sparql-results+json",
          "Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except Exception:
            if attempt==retries-1: raise
            time.sleep(2**attempt)
    return []

def qid(uri): return uri.rsplit("/",1)[-1]
def rank(uri): return uri.rsplit("#",1)[-1].replace("Rank","").lower()

def main():
    if len(sys.argv)<2: raise SystemExit("cohort csv[.gz] required")
    src=Path(sys.argv[1])
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/wikidata_birth_assertions.ndjson")
    resume=Path(str(out)+".done")
    done=set(resume.read_text().splitlines()) if resume.exists() else set()
    qids=[q for q in dict.fromkeys(read_qids(src)) if q not in done]
    out.parent.mkdir(parents=True,exist_ok=True)
    mode="a" if out.exists() else "w"
    fetched=written=0
    with out.open(mode,encoding="utf-8") as w, resume.open("a",encoding="utf-8") as d:
        for batch in chunks(qids,BATCH):
            bindings=query(batch)
            grouped={q:[] for q in batch}
            for b in bindings:
                q=qid(b["item"]["value"])
                row={
                  "assertion_id":f"wd:{q}:P569:{len(grouped.setdefault(q,[]))}",
                  "person_id":f"wd:{q}",
                  "date_iso":b["time"]["value"],
                  "date_precision":int(b["precision"]["value"]),
                  "source_id":"wikidata",
                  "source_reliability":"structured-statement",
                  "rank":rank(b["rank"]["value"]),
                  "status":"unresolved"
                }
                grouped[q].append(row)
            for q in batch:
                rows=grouped.get(q,[])
                distinct={(x["date_iso"],x["date_precision"]) for x in rows}
                for x in rows:
                    x["status"]="conflicting" if len(distinct)>1 else "single-source"
                    w.write(json.dumps(x,ensure_ascii=False)+"\n"); written+=1
                d.write(q+"\n"); fetched+=1
            w.flush();d.flush()
            print(f"fetched={fetched:,}/{len(qids):,} assertions={written:,}",file=sys.stderr)
            time.sleep(.35)
    print(f"done qids={fetched:,} assertions={written:,} -> {out}")

if __name__=="__main__": main()
