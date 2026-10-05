"""Build family.child_birth events from Wikidata P40 -> child P569.

This is a strict two-hop structured enrichment:
  person QID --P40--> child QID --P569--> child birth date

No name matching and no biography inference. Conflicting child birth assertions are skipped.
Output already follows the common LifeGraph event contract.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from calendar import monthrange
from collections import defaultdict
from datetime import date
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
GREGORIAN="Q1985727"
JULIAN="Q1985786"

def post_json(params,retries=8):
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(API,data=data,headers={
          "User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"
        })
        try:
            with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504):raise
            retry=e.headers.get("Retry-After")
            try:delay=float(retry) if retry else min(120,max(5,2**a))+random.random()
            except:delay=min(120,max(5,2**a))+random.random()
            if a==retries-1:raise
            time.sleep(delay)
        except Exception:
            if a==retries-1:raise
            time.sleep(min(60,max(3,2**a))+random.random())

def get_entities(qids):
    if not qids:return {}
    return post_json({
      "action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
      "ids":"|".join(qids),"props":"claims"
    }).get("entities",{})

def read_qids(path,id_column):
    out=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or r.get("wikidata_id") or r.get("wikidata_code") or "").strip()
            if q.startswith("Q") and q[1:].isdigit():out.append(q)
    return sorted(set(out),key=lambda x:int(x[1:]))

def read_births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or r.get("person_id") or "").strip()
            raw=(r.get("birth_date") or r.get("birth_date_normalized") or "")[:10]
            try:
                if q and raw:out[q]=date.fromisoformat(raw)
            except:pass
    return out

def item_values(ent,prop):
    vals=[]
    for c in ent.get("claims",{}).get(prop,[]):
        if c.get("rank")=="deprecated":continue
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and v.get("entity-type")=="item" and v.get("id"):
            vals.append((v["id"],c.get("id"),len(c.get("references",[]))))
    return vals

def julian_to_gregorian(y,m,d):
    a=(14-m)//12;yy=y+4800-a;mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044;b=(4*a+3)//146097;c=a-(146097*b)//4
    dd=(4*c+3)//1461;e=c-(1461*dd)//4;mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1;month=mm2+3-12*(mm2//10);year=100*b+dd-4800+(mm2//10)
    return date(year,month,day)

def parse_wikidata_time(v):
    raw=v.get("time") or "";precision=int(v.get("precision") or 0)
    cal=(v.get("calendarmodel") or "").rsplit("/",1)[-1]
    try:
        ds=raw.lstrip("+").split("T",1)[0]
        y,m,d=map(int,ds.split("-")[:3])
        if y<=0 or y>9999 or precision<9:return None
    except:return None

    if precision==9:
        if cal==JULIAN:
            lo=julian_to_gregorian(y,1,1);hi=julian_to_gregorian(y,12,31)
        else:
            lo=date(y,1,1);hi=date(y,12,31)
        return lo,hi,"year",raw,cal
    if precision==10:
        try:
            if cal==JULIAN:
                last=29 if m==2 and y%4==0 else (28 if m==2 else (30 if m in {4,6,9,11} else 31))
                lo=julian_to_gregorian(y,m,1);hi=julian_to_gregorian(y,m,last)
            else:
                lo=date(y,m,1);hi=date(y,m,monthrange(y,m)[1])
            return lo,hi,"month",raw,cal
        except:return None
    try:
        d0=julian_to_gregorian(y,m,d) if cal==JULIAN else date(y,m,d)
        return d0,d0,"day",raw,cal
    except:return None

def birth_assertions(ent):
    out=[]
    for c in ent.get("claims",{}).get("P569",[]):
        if c.get("rank")=="deprecated":continue
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if not isinstance(v,dict):continue
        parsed=parse_wikidata_time(v)
        if not parsed:continue
        out.append((parsed,c.get("rank") or "normal",c.get("id"),len(c.get("references",[]))))
    return out

def choose_birth(assertions):
    if not assertions:return None,"missing"
    # Preferred rank first, then highest temporal precision (day > month > year).
    score={"day":3,"month":2,"year":1}
    best_rank=1 if any(x[1]=="preferred" for x in assertions) else 0
    candidates=[x for x in assertions if (1 if x[1]=="preferred" else 0)==best_rank]
    maxprec=max(score[x[0][2]] for x in candidates)
    candidates=[x for x in candidates if score[x[0][2]]==maxprec]
    intervals={(x[0][0],x[0][1]) for x in candidates}
    if len(intervals)!=1:return None,"conflicting"
    return candidates[0],"ok"

def age(b,d):return round((d-b).days/365.2425,4)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cohort");ap.add_argument("canonical_births");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--batch-size",type=int,default=40)
    ap.add_argument("--sleep",type=float,default=.2)
    args=ap.parse_args()

    qids=read_qids(Path(args.cohort),args.id_column)
    parent_births=read_births(Path(args.canonical_births))
    relations=[];children=set();failed_parent_batches=0
    for i in range(0,len(qids),args.batch_size):
        batch=qids[i:i+args.batch_size]
        try:ents=get_entities(batch)
        except Exception as e:
            failed_parent_batches+=1;print(f"warning parent batch failed {i}: {e!r}",flush=True);continue
        for q in batch:
            for child,statement_id,refs in item_values(ents.get(q,{}),"P40"):
                relations.append((q,child,statement_id,refs));children.add(child)
        time.sleep(args.sleep)

    child_entities={};failed_child_batches=0
    child_ids=sorted(children,key=lambda x:int(x[1:]) if x[1:].isdigit() else x)
    for i in range(0,len(child_ids),args.batch_size):
        batch=child_ids[i:i+args.batch_size]
        try:child_entities.update(get_entities(batch))
        except Exception as e:
            failed_child_batches+=1;print(f"warning child batch failed {i}: {e!r}",flush=True)
        time.sleep(args.sleep)

    fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max",
            "temporal_precision","age_min","age_max","age_mid","subject_id","source_id",
            "source_url","extraction_method","confidence","observable_from","attributes_json"]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=0;people=set();missing_parent_birth=0;missing_child_birth=0;conflicting_child_birth=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for parent,child,rel_statement,rel_refs in relations:
            pb=parent_births.get(parent)
            if not pb:missing_parent_birth+=1;continue
            chosen,status=choose_birth(birth_assertions(child_entities.get(child,{})))
            if status=="missing":missing_child_birth+=1;continue
            if status=="conflicting":conflicting_child_birth+=1;continue
            parsed,rank,birth_statement,birth_refs=chosen
            lo,hi,prec,raw,cal=parsed
            amin=age(pb,lo);amax=age(pb,hi);amid=round((amin+amax)/2,4)
            conf=min(.97,.78+.03*min(rel_refs,3)+.03*min(birth_refs,3)+(.04 if rank=="preferred" else 0))
            wr.writerow({
              "event_id":f"{parent}:wikidata:P40:{child}","person_id":parent,"domain":"family",
              "event_type":"family.child_birth","event_date_min":lo.isoformat(),"event_date_max":hi.isoformat(),
              "temporal_precision":prec,"age_min":amin,"age_max":amax,"age_mid":amid,
              "subject_id":child,"source_id":"wikidata",
              "source_url":f"https://www.wikidata.org/wiki/{child}",
              "extraction_method":"structured-two-hop","confidence":conf,
              "observable_from":hi.isoformat(),
              "attributes_json":json.dumps({
                "relationship_statement_id":rel_statement,"child_birth_statement_id":birth_statement,
                "relationship_reference_count":rel_refs,"birth_reference_count":birth_refs,
                "birth_rank":rank,"source_time_raw":raw,"calendar_model":cal
              },separators=(",",":"))
            })
            rows+=1;people.add(parent)
    report={
      "input_people":len(qids),"parent_child_relations":len(relations),"unique_children":len(children),
      "people_with_child_birth_events":len(people),"family_child_birth_events":rows,
      "missing_parent_birth_rows":missing_parent_birth,"missing_child_birth_rows":missing_child_birth,
      "conflicting_child_birth_rows":conflicting_child_birth,
      "failed_parent_batches":failed_parent_batches,"failed_child_batches":failed_child_batches,
      "identity_path":"parent P40 child QID -> child P569; no fuzzy names"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
