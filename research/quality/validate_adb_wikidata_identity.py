"""Validate Astro -> Wikipedia -> Wikidata identity links using birth-date agreement.

A Wikipedia link resolving to a QID is not enough: family-member and namesake records can point
at the wrong article. For the primary timed training cohort, a QID is accepted only when at
least one non-deprecated Wikidata P569 day-level assertion matches the normalized physical
birth date used by the BaZi feature engine.

This makes identity linkage a falsifiable data-quality gate rather than a URL assumption.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from datetime import date
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
GREGORIAN="Q1985727";JULIAN="Q1985786"

def read(path,key):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            k=(r.get(key) or "").strip()
            if k:out[k]=r
    return out

def get_entities(qids,retries=10):
    params={"action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
            "ids":"|".join(qids),"props":"claims"}
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(API,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req,timeout=120) as r:
                return json.load(r).get("entities",{})
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or a==retries-1:
                raise
            retry=e.headers.get("Retry-After")
            try:
                delay=float(retry) if retry else min(120,max(4,2**a))+random.random()
            except Exception:
                delay=min(120,max(4,2**a))+random.random()
            time.sleep(delay)
        except Exception:
            if a==retries-1:
                raise
            time.sleep(min(90,max(3,2**a))+random.random())

def get_entities_lossless(qids):
    """Fetch all possible entities, recursively splitting any persistently failing batch.

    A transient failure must never silently erase an entire 40-QID identity batch. A single
    entity is counted as failed only after it has exhausted the full retry policy on its own.
    """
    try:
        return get_entities(qids), []
    except Exception as exc:
        if len(qids)==1:
            print(f"identity single-qid failed {qids[0]}: {exc!r}",flush=True)
            return {}, list(qids)
        mid=len(qids)//2
        left,lf=get_entities_lossless(qids[:mid])
        time.sleep(.25+random.random()*.25)
        right,rf=get_entities_lossless(qids[mid:])
        left.update(right)
        return left,lf+rf

def julian_to_gregorian(y,m,d):
    a=(14-m)//12;yy=y+4800-a;mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044;b=(4*a+3)//146097;c=a-(146097*b)//4
    dd=(4*c+3)//1461;e=c-(1461*dd)//4;mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1;month=mm2+3-12*(mm2//10);year=100*b+dd-4800+(mm2//10)
    return date(year,month,day)

def normalized_time_claims(ent,prop):
    exact=[];coarse=[];raw=[]
    for claim in ent.get("claims",{}).get(prop,[]):
        if claim.get("rank")=="deprecated":continue
        v=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
        if not isinstance(v,dict) or not v.get("time"):continue
        precision=int(v.get("precision") or 0)
        t=v["time"];cal=(v.get("calendarmodel") or "").rsplit("/",1)[-1]
        raw.append({"time":t,"precision":precision,"calendar":cal,"rank":claim.get("rank")})
        try:
            ds=t.lstrip("+").split("T",1)[0]
            y,m,d=map(int,ds.split("-")[:3])
            if y<=0:continue
        except Exception:
            continue
        if precision<11:
            coarse.append((y,m if precision>=10 else None))
            continue
        try:
            physical=julian_to_gregorian(y,m,d) if cal==JULIAN else date(y,m,d)
            exact.append(physical.isoformat())
        except Exception:
            continue
    return sorted(set(exact)),coarse,raw

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("astro_births");ap.add_argument("links");ap.add_argument("bazi_features");ap.add_argument("output")
    ap.add_argument("--batch-size",type=int,default=40);ap.add_argument("--sleep",type=float,default=.15)
    args=ap.parse_args()
    births=read(Path(args.astro_births),"adb_id");features=read(Path(args.bazi_features),"person_id")
    link_rows=[]
    with gzip.open(args.links,"rt",encoding="utf-8",newline="") as f:
        link_rows=list(csv.DictReader(f))
    qids=sorted({r["wikidata_id"] for r in link_rows if r.get("wikidata_id") and r["wikidata_id"].startswith("Q")},
                key=lambda x:int(x[1:]))
    entities={};failed_qids=[]
    for i in range(0,len(qids),args.batch_size):
        batch=qids[i:i+args.batch_size]
        got,failed=get_entities_lossless(batch)
        entities.update(got);failed_qids.extend(failed)
        if (i//args.batch_size+1)%20==0:
            print(f"identity_qids={min(i+args.batch_size,len(qids))}/{len(qids)} failed_so_far={len(failed_qids)}",flush=True)
        time.sleep(args.sleep)
    failures=len(set(failed_qids))

    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["adb_id","rodden_rating","wikidata_id","wikipedia_url","astro_birth_date_normalized",
            "wikidata_day_dates","identity_status","matching_date","wikidata_birth_assertions_json",
            "wikidata_death_exact_dates","wikidata_death_years","wikidata_death_assertions_json"]
    counts=defaultdict(int);verified_q=defaultdict(list)
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for l in link_rows:
            aid=l.get("adb_id","");q=l.get("wikidata_id","")
            f=features.get(aid);b=births.get(aid)
            normalized=f.get("birth_date","") if f else ""
            ent=entities.get(q,{}) if q else {}
            exact,coarse,raw=normalized_time_claims(ent,"P569") if q else ([],[],[])
            death_exact,death_coarse,death_raw=normalized_time_claims(ent,"P570") if q else ([],[],[])
            death_years=sorted({int(x["time"].lstrip("+").split("-",1)[0]) for x in death_raw
                                if x.get("time") and x["time"].lstrip("+").split("-",1)[0].isdigit()})
            if not q:status="no_qid"
            elif not f:status="no_primary_bazi_feature"
            elif normalized in exact:status="verified_day_match"
            elif exact:status="day_mismatch"
            elif coarse:status="insufficient_birth_precision"
            else:status="wikidata_birth_missing"
            counts[status]+=1
            if status=="verified_day_match":verified_q[q].append(aid)
            wr.writerow({
              "adb_id":aid,"rodden_rating":(b or {}).get("rodden_rating",l.get("rodden_rating","")),
              "wikidata_id":q,"wikipedia_url":l.get("wikipedia_url",""),
              "astro_birth_date_normalized":normalized,
              "wikidata_day_dates":"|".join(exact),"identity_status":status,
              "matching_date":normalized if status=="verified_day_match" else "",
              "wikidata_birth_assertions_json":json.dumps(raw,separators=(",",":")),
              "wikidata_death_exact_dates":"|".join(death_exact),
              "wikidata_death_years":"|".join(map(str,death_years)),
              "wikidata_death_assertions_json":json.dumps(death_raw,separators=(",",":"))
            })
    duplicate_verified={q:a for q,a in verified_q.items() if len(a)>1}
    report={
      "link_rows":len(link_rows),"unique_qids_requested":len(qids),"api_failure_qids":failures,
      "status_counts":dict(counts),"verified_qids":len(verified_q),
      "verified_duplicate_qids":len(duplicate_verified),
      "verified_duplicate_examples":dict(list(duplicate_verified.items())[:20]),
      "failed_qids":sorted(set(failed_qids),key=lambda x:int(x[1:])) if failed_qids else [],
      "training_rule":"identity_status must equal verified_day_match; final training snapshot requires api_failure_qids == 0"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
