"""Resolve subject QIDs referenced by life events into compact semantic metadata.

Input: normalized life_events.csv.gz (subject_id column)
Output: subject_entities.csv.gz

We keep labels and shallow class information (P31/P279/P17/P625) so downstream models can
distinguish universities, companies, offices, awards, cities, parties, teams, etc. without
using raw QID identity as a high-cardinality memorization feature.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

def qid(v):
    v=(v or "").strip()
    return v if v.startswith("Q") and v[1:].isdigit() else None

def read_subjects(path:Path):
    s=set()
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=qid(r.get("subject_id"))
            if q:s.add(q)
    return sorted(s,key=lambda x:int(x[1:]))

def get_entities(qids,retries=6):
    params={
      "action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
      "ids":"|".join(qids),"props":"labels|descriptions|claims","languages":"en|zh|zh-hans"
    }
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(API,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req,timeout=90) as r:return json.load(r).get("entities",{})
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or a==retries-1:raise
            time.sleep(min(30,2**a)+random.random())
        except Exception:
            if a==retries-1:raise
            time.sleep(min(30,2**a)+random.random())

def item_values(ent,prop):
    out=[]
    for c in ent.get("claims",{}).get(prop,[]):
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and v.get("entity-type")=="item" and v.get("id"):out.append(v["id"])
    return sorted(set(out))

def coordinate(ent):
    for c in ent.get("claims",{}).get("P625",[]):
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "latitude" in v:
            return v.get("latitude"),v.get("longitude")
    return None,None

def label(ent,*langs):
    ls=ent.get("labels",{})
    for lang in langs:
        v=ls.get(lang,{}).get("value")
        if v:return v
    return ""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("events");ap.add_argument("output")
    ap.add_argument("--batch-size",type=int,default=40)
    ap.add_argument("--sleep",type=float,default=.15)
    args=ap.parse_args()
    ids=read_subjects(Path(args.events))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["qid","label_en","label_zh","description_en","instance_of","subclass_of","country","latitude","longitude"]
    written=fail=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for i in range(0,len(ids),args.batch_size):
            batch=ids[i:i+args.batch_size]
            try:ents=get_entities(batch)
            except Exception as e:
                print(f"failed batch {i}: {e!r}",flush=True);fail+=len(batch);continue
            for q in batch:
                e=ents.get(q,{})
                lat,lng=coordinate(e)
                wr.writerow({
                  "qid":q,"label_en":label(e,"en"),"label_zh":label(e,"zh-hans","zh"),
                  "description_en":e.get("descriptions",{}).get("en",{}).get("value",""),
                  "instance_of":"|".join(item_values(e,"P31")),"subclass_of":"|".join(item_values(e,"P279")),
                  "country":"|".join(item_values(e,"P17")),
                  "latitude":"" if lat is None else lat,"longitude":"" if lng is None else lng
                });written+=1
            if (i//args.batch_size+1)%20==0:print(f"resolved={min(i+args.batch_size,len(ids))}/{len(ids)}",flush=True)
            time.sleep(args.sleep)
    report={"unique_subject_qids":len(ids),"resolved_rows":written,"failed_qids":fail}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
