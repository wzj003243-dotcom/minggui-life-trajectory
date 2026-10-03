"""Fetch notable-work dates (P800 -> work item -> P577) as creation timeline events.

This intentionally uses only explicit notable-work links. It is not a complete bibliography,
but adds dated creation events for many artists/scientists without text inference.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

def get_entities(qids,props="claims",retries=6):
    params={"action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5","ids":"|".join(qids),"props":props}
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

def time_values(ent,prop):
    out=[]
    for c in ent.get("claims",{}).get(prop,[]):
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and v.get("time"):
            out.append({"time":v.get("time"),"precision":v.get("precision"),"calendar_model":v.get("calendarmodel"),
                        "rank":c.get("rank"),"reference_count":len(c.get("references",[]))})
    return out

def read_people(path,id_column):
    ids=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or "").strip()
            if q.startswith("Q") and q[1:].isdigit():ids.append(q)
    return sorted(set(ids),key=lambda x:int(x[1:]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("people");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--batch-size",type=int,default=40)
    args=ap.parse_args()
    people=read_people(Path(args.people),args.id_column)
    links=[];works_to_people={}
    for i in range(0,len(people),args.batch_size):
        batch=people[i:i+args.batch_size]
        ents=get_entities(batch)
        for p in batch:
            for w in item_values(ents.get(p,{}),"P800"):
                works_to_people.setdefault(w,set()).add(p)
        if (i//args.batch_size+1)%20==0:print(f"people={min(i+args.batch_size,len(people))}/{len(people)} works={len(works_to_people)}",flush=True)
        time.sleep(.1)
    work_ids=sorted(works_to_people,key=lambda x:int(x[1:]))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["person_id","event_type","work_qid","publication_json"]
    rows=0;with_dates=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as fw:
        wr=csv.DictWriter(fw,fieldnames=fields);wr.writeheader()
        for i in range(0,len(work_ids),args.batch_size):
            batch=work_ids[i:i+args.batch_size];ents=get_entities(batch)
            for wid in batch:
                dates=time_values(ents.get(wid,{}),"P577")
                if not dates:continue
                for pid in works_to_people[wid]:
                    wr.writerow({"person_id":pid,"event_type":"creation.notable_work","work_qid":wid,
                                 "publication_json":json.dumps(dates,separators=(",",":"))})
                    rows+=1;with_dates+=1
            time.sleep(.1)
    report={"input_people":len(people),"unique_notable_works":len(work_ids),"dated_creation_rows":rows}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
