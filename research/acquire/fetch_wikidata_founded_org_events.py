"""Fetch organization-founding events via inverse Wikidata P112 and organization P571.

Identity path:
  organization --P112 founded by--> person QID
  organization --P571 inception--> dated founding event

Uses WDQS in bounded QID batches. No name matching.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from calendar import monthrange
from datetime import date
from pathlib import Path

ENDPOINT="https://query.wikidata.org/sparql"
UA="MingGuiLifeTrajectory/0.1 (https://github.com/wzj003243-dotcom/minggui-life-trajectory; research)"
GREGORIAN="Q1985727";JULIAN="Q1985786"

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

def query_batch(qids,retries=8):
    values=" ".join("wd:"+q for q in qids)
    sparql=f"""
SELECT ?person ?org ?date ?precision ?calendar WHERE {{
  VALUES ?person {{ {values} }}
  ?org wdt:P112 ?person .
  ?org p:P571 ?stmt .
  ?stmt psv:P571 ?v .
  ?v wikibase:timeValue ?date ;
     wikibase:timePrecision ?precision ;
     wikibase:timeCalendarModel ?calendar .
}}
"""
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
                return query_batch(qids[:mid],retries)+query_batch(qids[mid:],retries)
            if e.code not in (429,500,502,503,504) or a==retries-1:
                if len(qids)>1:
                    mid=len(qids)//2
                    return query_batch(qids[:mid],retries)+query_batch(qids[mid:],retries)
                return []
            retry=e.headers.get("Retry-After")
            try:delay=float(retry) if retry else min(90,max(5,2**a))+random.random()
            except:delay=min(90,max(5,2**a))+random.random()
            time.sleep(delay)
        except Exception:
            if a==retries-1:
                if len(qids)>1:
                    mid=len(qids)//2
                    return query_batch(qids[:mid],retries)+query_batch(qids[mid:],retries)
                return []
            time.sleep(min(60,max(3,2**a))+random.random())

def julian_to_gregorian(y,m,d):
    a=(14-m)//12;yy=y+4800-a;mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044;b=(4*a+3)//146097;c=a-(146097*b)//4
    dd=(4*c+3)//1461;e=c-(1461*dd)//4;mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1;month=mm2+3-12*(mm2//10);year=100*b+dd-4800+(mm2//10)
    return date(year,month,day)

def interval(raw,precision,calendar):
    try:
        ds=raw.lstrip("+").split("T",1)[0]
        y,m,d=map(int,ds.split("-")[:3]);p=int(precision)
        cal=(calendar or "").rsplit("/",1)[-1]
        if y<=0 or y>9999 or p<9:return None
    except:return None
    try:
        if p==9:
            if cal==JULIAN:return julian_to_gregorian(y,1,1),julian_to_gregorian(y,12,31),"year"
            return date(y,1,1),date(y,12,31),"year"
        if p==10:
            if cal==JULIAN:
                last=29 if m==2 and y%4==0 else (28 if m==2 else (30 if m in {4,6,9,11} else 31))
                return julian_to_gregorian(y,m,1),julian_to_gregorian(y,m,last),"month"
            return date(y,m,1),date(y,m,monthrange(y,m)[1]),"month"
        d0=julian_to_gregorian(y,m,d) if cal==JULIAN else date(y,m,d)
        return d0,d0,"day"
    except:return None

def age(b,d):return round((d-b).days/365.2425,4)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cohort");ap.add_argument("canonical_births");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--batch-size",type=int,default=80)
    ap.add_argument("--sleep",type=float,default=.35)
    args=ap.parse_args()

    qids=read_qids(Path(args.cohort),args.id_column);births=read_births(Path(args.canonical_births))
    bindings=[];failed_batches=0
    for i in range(0,len(qids),args.batch_size):
        batch=qids[i:i+args.batch_size]
        try:bindings.extend(query_batch(batch))
        except Exception as e:
            failed_batches+=1;print(f"warning founding batch failed {i}: {e!r}",flush=True)
        if (i//args.batch_size+1)%10==0:
            print(f"founder_qids={min(i+args.batch_size,len(qids))}/{len(qids)} raw_rows={len(bindings)}",flush=True)
        time.sleep(args.sleep)

    fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max",
            "temporal_precision","age_min","age_max","age_mid","subject_id","source_id",
            "source_url","extraction_method","confidence","observable_from","attributes_json"]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    seen=set();rows=0;people=set();invalid=missing_birth=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for b in bindings:
            pid=b["person"]["value"].rsplit("/",1)[-1]
            org=b["org"]["value"].rsplit("/",1)[-1]
            raw=b["date"]["value"];prec=b["precision"]["value"];cal=b["calendar"]["value"]
            x=interval(raw,prec,cal)
            if not x:invalid+=1;continue
            pb=births.get(pid)
            if not pb:missing_birth+=1;continue
            lo,hi,label=x
            eid=f"{pid}:wikidata:P112:{org}:{lo.isoformat()}:{hi.isoformat()}"
            if eid in seen:continue
            seen.add(eid)
            amin=age(pb,lo);amax=age(pb,hi);amid=round((amin+amax)/2,4)
            wr.writerow({
              "event_id":eid,"person_id":pid,"domain":"creation",
              "event_type":"creation.organization_founded",
              "event_date_min":lo.isoformat(),"event_date_max":hi.isoformat(),
              "temporal_precision":label,"age_min":amin,"age_max":amax,"age_mid":amid,
              "subject_id":org,"source_id":"wikidata",
              "source_url":f"https://www.wikidata.org/wiki/{org}",
              "extraction_method":"structured-inverse-two-hop","confidence":0.90,
              "observable_from":hi.isoformat(),
              "attributes_json":json.dumps({"source_time_raw":raw,"calendar_model":cal},separators=(",",":"))
            })
            rows+=1;people.add(pid)
    report={
      "input_people":len(qids),"people_with_founding_events":len(people),
      "organization_founding_events":rows,"raw_bindings":len(bindings),
      "invalid_time_rows":invalid,"missing_parent_birth_rows":missing_birth,
      "failed_batches":failed_batches,
      "identity_path":"organization P112 founded by person -> organization P571 inception"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
