"""Enrich a Wikidata cohort with music-creator timeline events via P434 -> MusicBrainz.

Identity path:
  Wikidata QID -> exact P434 MusicBrainz Artist ID -> MusicBrainz browse endpoints.

No fuzzy artist-name matching.

MusicBrainz asks clients to stay at or below one web-service request per second; this script
uses >=1.1s between requests.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

WD="https://www.wikidata.org/w/api.php"
MB="https://musicbrainz.org/ws/2"
UA="MingGuiLifeTrajectory/0.1 ( github.com/wzj003243-dotcom/minggui-life-trajectory )"

def post_json(url,params,retries=8):
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"})
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

def get_json(url,params,retries=8):
    target=url+"?"+urllib.parse.urlencode(params)
    for a in range(retries):
        req=urllib.request.Request(target,headers={"User-Agent":UA,"Accept":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504):raise
            retry=e.headers.get("Retry-After")
            try:delay=float(retry) if retry else min(120,max(8,2**a))+random.random()
            except:delay=min(120,max(8,2**a))+random.random()
            if a==retries-1:raise
            time.sleep(delay)
        except Exception:
            if a==retries-1:raise
            time.sleep(min(60,max(4,2**a))+random.random())

def read_qids(path,id_column,limit):
    ids=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or r.get("wikidata_id") or r.get("wikidata_code") or "").strip()
            if q.startswith("Q") and q[1:].isdigit():ids.append(q)
    ids=sorted(set(ids),key=lambda x:int(x[1:]))
    return ids[:limit] if limit>0 else ids

def wikidata_musicbrainz(qids,batch_size=40):
    out=defaultdict(set)
    for i in range(0,len(qids),batch_size):
        batch=qids[i:i+batch_size]
        data=post_json(WD,{"action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
                           "ids":"|".join(batch),"props":"claims"})
        for q,e in data.get("entities",{}).items():
            for claim in e.get("claims",{}).get("P434",[]):
                if claim.get("rank")=="deprecated":continue
                v=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
                if isinstance(v,str) and len(v)==36:out[q].add(v)
        time.sleep(.2)
    return out

def browse(resource,artist_id):
    offset=0
    while True:
        data=get_json(f"{MB}/{resource}",{"artist":artist_id,"fmt":"json","limit":100,"offset":offset})
        key={"release-group":"release-groups","event":"events"}[resource]
        rows=data.get(key) or []
        for x in rows:yield x
        count=data.get("count") or len(rows)
        offset+=len(rows)
        time.sleep(1.1)
        if not rows or offset>=count:break

def main():
    ap=argparse.ArgumentParser();ap.add_argument("cohort");ap.add_argument("output_dir")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--limit",type=int,default=3000)
    args=ap.parse_args()
    outdir=Path(args.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    qids=read_qids(Path(args.cohort),args.id_column,args.limit)
    q_to_mb=wikidata_musicbrainz(qids)
    primary={q:next(iter(v)) for q,v in q_to_mb.items() if len(v)==1}
    ambiguous={q:sorted(v) for q,v in q_to_mb.items() if len(v)>1}

    fields=["event_id","person_id","event_type","event_date","musicbrainz_id","title","subtype","source_id","source_url","identity_method"]
    events=0;people=set();releases=performances=0;failures=0
    path=outdir/"music_events.csv.gz"
    with gzip.open(path,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for n,(q,mbid) in enumerate(primary.items(),1):
            try:
                for x in browse("release-group",mbid):
                    d=x.get("first-release-date") or ""
                    if not d:continue
                    rgid=x.get("id") or ""
                    wr.writerow({
                      "event_id":f"{q}:musicbrainz:release-group:{rgid}","person_id":q,
                      "event_type":"creation.music_release_group","event_date":d,
                      "musicbrainz_id":rgid,"title":x.get("title") or "",
                      "subtype":x.get("primary-type") or "","source_id":"musicbrainz",
                      "source_url":f"https://musicbrainz.org/release-group/{rgid}",
                      "identity_method":"wikidata_p434_exact_mbid"
                    });events+=1;releases+=1;people.add(q)
                for x in browse("event",mbid):
                    span=x.get("life-span") or {};d=span.get("begin") or ""
                    if not d:continue
                    eid=x.get("id") or ""
                    wr.writerow({
                      "event_id":f"{q}:musicbrainz:event:{eid}","person_id":q,
                      "event_type":"performance.music_event","event_date":d,
                      "musicbrainz_id":eid,"title":x.get("name") or "",
                      "subtype":x.get("type") or "","source_id":"musicbrainz",
                      "source_url":f"https://musicbrainz.org/event/{eid}",
                      "identity_method":"wikidata_p434_exact_mbid"
                    });events+=1;performances+=1;people.add(q)
            except Exception as e:
                failures+=1;print(f"warning: musicbrainz person failed {q}/{mbid}: {e!r}",flush=True)
            if n%20==0:print(f"musicbrainz_people={n}/{len(primary)} events={events}",flush=True)

    report={
      "input_qids":len(qids),"people_with_p434":len(q_to_mb),"single_mbid_people":len(primary),
      "ambiguous_p434_people":len(ambiguous),"people_with_dated_music_events":len(people),
      "dated_event_rows":events,"release_group_events":releases,"performance_events":performances,
      "person_failures":failures,"identity_method":"Wikidata P434 exact MusicBrainz artist id",
      "rate_limit_policy":">=1.1 seconds between MusicBrainz browse requests"
    }
    (outdir/"music_enrichment.report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
