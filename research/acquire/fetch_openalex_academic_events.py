"""Enrich a Wikidata QID cohort with scholarly life events through ORCID -> OpenAlex.

Identity path is deliberately strict:
  Wikidata person QID -> P496 ORCID -> exact OpenAlex ORCID match -> OpenAlex works.

No fuzzy name matching is used.

Outputs:
  academic_events.csv.gz
  academic_authors.csv.gz
  *.report.json

Only publication-time facts are emitted as model-safe event features. Current citation totals are
kept out of the event table because they contain future information relative to historical cutoffs.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,re,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

WD="https://www.wikidata.org/w/api.php"
OA="https://api.openalex.org"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
ORCID_RE=re.compile(r"^\d{4}-\d{4}-\d{4}-[\dX]{4}$",re.I)

def get_json(url,params,retries=8):
    qs=urllib.parse.urlencode(params,safe="|,:/")
    target=url+"?"+qs
    for a in range(retries):
        req=urllib.request.Request(target,headers={"User-Agent":UA,"Accept":"application/json"})
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

def post_json(url,params,retries=8):
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
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

def read_qids(path,id_column,limit):
    out=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or r.get("wikidata_id") or r.get("wikidata_code") or "").strip()
            if q.startswith("Q") and q[1:].isdigit():out.append(q)
    out=sorted(set(out),key=lambda x:int(x[1:]))
    return out[:limit] if limit>0 else out

def wikidata_orcids(qids,batch_size=40):
    out=defaultdict(set)
    for i in range(0,len(qids),batch_size):
        batch=qids[i:i+batch_size]
        data=post_json(WD,{"action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
                           "ids":"|".join(batch),"props":"claims"})
        for q,e in data.get("entities",{}).items():
            for claim in e.get("claims",{}).get("P496",[]):
                if claim.get("rank")=="deprecated":continue
                v=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
                if isinstance(v,str):
                    v=v.replace("https://orcid.org/","").upper().strip()
                    if ORCID_RE.match(v):out[q].add(v)
        if (i//batch_size+1)%20==0:print(f"wikidata_orcid={min(i+batch_size,len(qids))}/{len(qids)}",flush=True)
        time.sleep(.2)
    return out

def norm_orcid(v):
    return (v or "").replace("https://orcid.org/","").upper().strip()

def resolve_openalex(orcid_to_qids,batch_size=50):
    mapping={};ambiguous=defaultdict(list)
    all_orcids=sorted(orcid_to_qids)
    for i in range(0,len(all_orcids),batch_size):
        batch=all_orcids[i:i+batch_size]
        data=get_json(OA+"/authors",{
          "filter":"orcid:"+"|".join(batch),"per_page":100,
          "select":"id,display_name,orcid,works_count,cited_by_count"
        })
        by_orcid=defaultdict(list)
        for a in data.get("results",[]):
            o=norm_orcid(a.get("orcid"))
            if o:by_orcid[o].append(a)
        for o in batch:
            hits=by_orcid.get(o,[])
            if len(hits)==1:mapping[o]=hits[0]
            elif len(hits)>1:ambiguous[o]=hits
        if (i//batch_size+1)%10==0:print(f"openalex_authors={min(i+batch_size,len(all_orcids))}/{len(all_orcids)}",flush=True)
        time.sleep(.15)
    return mapping,ambiguous

def work_pages(author_id,max_works):
    cursor="*";yielded=0
    while cursor and yielded<max_works:
        data=get_json(OA+"/works",{
          "filter":f"authorships.author.id:{author_id}",
          "per_page":100,"cursor":cursor,
          "select":"id,doi,title,publication_date,publication_year,type,authorships,primary_topic"
        })
        results=data.get("results",[])
        if not results:break
        for w in results:
            if yielded>=max_works:break
            yield w;yielded+=1
        cursor=data.get("meta",{}).get("next_cursor")
        time.sleep(.08)

def author_affiliation(work,author_id):
    for a in work.get("authorships") or []:
        aid=((a.get("author") or {}).get("id") or "").rsplit("/",1)[-1]
        if aid==author_id:
            inst=a.get("institutions") or []
            return {
              "author_position":a.get("author_position"),
              "is_corresponding":a.get("is_corresponding"),
              "institution_ids":"|".join((x.get("id") or "").rsplit("/",1)[-1] for x in inst if x.get("id")),
              "institution_names":"|".join(x.get("display_name") or "" for x in inst if x.get("display_name")),
              "institution_countries":"|".join(sorted({x.get("country_code") for x in inst if x.get("country_code")}))
            }
    return {"author_position":None,"is_corresponding":None,"institution_ids":"","institution_names":"","institution_countries":""}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cohort");ap.add_argument("output_dir")
    ap.add_argument("--id-column",default="wikidata_id")
    ap.add_argument("--limit",type=int,default=3000)
    ap.add_argument("--max-works-per-author",type=int,default=500)
    args=ap.parse_args()
    outdir=Path(args.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    qids=read_qids(Path(args.cohort),args.id_column,args.limit)
    q_to_orcids=wikidata_orcids(qids)
    orcid_to_qids=defaultdict(set)
    for q,os in q_to_orcids.items():
        for o in os:orcid_to_qids[o].add(q)
    oa_map,ambiguous=resolve_openalex(orcid_to_qids)

    author_fields=["person_id","orcid","openalex_author_id","display_name","works_count_current","cited_by_count_current","identity_method"]
    event_fields=["event_id","person_id","event_type","event_date","openalex_work_id","doi","title","work_type",
                  "author_position","is_corresponding","institution_ids","institution_names","institution_countries",
                  "primary_topic_id","primary_topic_name","primary_field_id","primary_field_name",
                  "source_id","source_url","identity_method"]
    author_rows=[];event_rows=0;people_with_works=set();truncated=0
    events_path=outdir/"academic_events.csv.gz"
    with gzip.open(events_path,"wt",encoding="utf-8",newline="") as ew:
        wr=csv.DictWriter(ew,fieldnames=event_fields);wr.writeheader()
        for o,a in oa_map.items():
            qids_for_o=orcid_to_qids[o]
            if len(qids_for_o)!=1:
                # Same ORCID should not belong to multiple Wikidata people in primary data.
                continue
            q=next(iter(qids_for_o))
            aid=(a.get("id") or "").rsplit("/",1)[-1]
            if not aid:continue
            author_rows.append({
              "person_id":q,"orcid":o,"openalex_author_id":aid,"display_name":a.get("display_name"),
              "works_count_current":a.get("works_count"),"cited_by_count_current":a.get("cited_by_count"),
              "identity_method":"wikidata_p496_exact_orcid"
            })
            count=0
            for w in work_pages(aid,args.max_works_per_author):
                date=w.get("publication_date")
                if not date:continue
                aff=author_affiliation(w,aid)
                topic=w.get("primary_topic") or {};field=topic.get("field") or {}
                wid=(w.get("id") or "").rsplit("/",1)[-1]
                wr.writerow({
                  "event_id":f"{q}:openalex:{wid}","person_id":q,"event_type":"creation.scholar_work",
                  "event_date":date,"openalex_work_id":wid,"doi":w.get("doi") or "",
                  "title":w.get("title") or "","work_type":w.get("type") or "",**aff,
                  "primary_topic_id":(topic.get("id") or "").rsplit("/",1)[-1],
                  "primary_topic_name":topic.get("display_name") or "",
                  "primary_field_id":(field.get("id") or "").rsplit("/",1)[-1],
                  "primary_field_name":field.get("display_name") or "",
                  "source_id":"openalex","source_url":w.get("id") or "",
                  "identity_method":"wikidata_p496_exact_orcid"
                })
                count+=1;event_rows+=1;people_with_works.add(q)
            if (a.get("works_count") or 0)>args.max_works_per_author:truncated+=1
            if len(author_rows)%50==0:print(f"academic_authors={len(author_rows)} events={event_rows}",flush=True)

    authors_path=outdir/"academic_authors.csv.gz"
    with gzip.open(authors_path,"wt",encoding="utf-8",newline="") as aw:
        wr=csv.DictWriter(aw,fieldnames=author_fields);wr.writeheader();wr.writerows(author_rows)
    report={
      "input_qids":len(qids),"people_with_wikidata_orcid":len(q_to_orcids),
      "unique_orcids":len(orcid_to_qids),"openalex_exact_orcid_authors":len(author_rows),
      "ambiguous_openalex_orcids":len(ambiguous),"people_with_scholarly_events":len(people_with_works),
      "scholarly_event_rows":event_rows,"authors_truncated_at_work_cap":truncated,
      "max_works_per_author":args.max_works_per_author,
      "identity_method":"Wikidata P496 ORCID -> exact OpenAlex ORCID; no fuzzy names",
      "leakage_note":"Current works_count/cited_by_count are stored only in author audit metadata and must not be used at historical cutoffs."
    }
    (outdir/"academic_enrichment.report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
