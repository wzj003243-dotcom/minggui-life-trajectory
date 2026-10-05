"""Enrich scholarly events from exact Wikidata P10283 -> OpenAlex author IDs.

This complements the ORCID path. It performs no name matching. The input bridge is produced by
fetch_wikidata_external_ids.py --property P10283 and must map a person QID to an OpenAlex A-id.
"""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from pathlib import Path
from research.acquire.fetch_openalex_academic_events import OA,get_json,work_pages,author_affiliation,read_qids

def read_bridge(path,allowed):
    out=defaultdict(set)
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or "").strip()
            x=(r.get("external_id") or "").strip().upper()
            if q in allowed and x.startswith("A") and x[1:].isdigit():out[q].add(x)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cohort");ap.add_argument("bridge");ap.add_argument("output_dir")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--limit",type=int,default=0)
    ap.add_argument("--max-works-per-author",type=int,default=300)
    args=ap.parse_args()
    outdir=Path(args.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    qids=set(read_qids(Path(args.cohort),args.id_column,args.limit))
    bridge=read_bridge(Path(args.bridge),qids)
    primary={q:next(iter(ids)) for q,ids in bridge.items() if len(ids)==1}

    afields=["person_id","openalex_author_id","display_name","works_count_current","cited_by_count_current","identity_method"]
    efields=["event_id","person_id","event_type","event_date","openalex_work_id","doi","title","work_type",
             "author_position","is_corresponding","institution_ids","institution_names","institution_countries",
             "primary_topic_id","primary_topic_name","primary_field_id","primary_field_name",
             "source_id","source_url","identity_method"]
    authors=[];events=0;people=set();failed=0;truncated=0
    with gzip.open(outdir/"academic_events_p10283.csv.gz","wt",encoding="utf-8",newline="") as ew:
        wr=csv.DictWriter(ew,fieldnames=efields);wr.writeheader()
        for n,(q,aid) in enumerate(primary.items(),1):
            try:
                a=get_json(OA+"/authors/"+aid,{"select":"id,display_name,orcid,works_count,cited_by_count"})
                got=(a.get("id") or "").rsplit("/",1)[-1]
                if got!=aid:continue
                authors.append({"person_id":q,"openalex_author_id":aid,"display_name":a.get("display_name"),
                                "works_count_current":a.get("works_count"),"cited_by_count_current":a.get("cited_by_count"),
                                "identity_method":"wikidata_p10283_exact_openalex"})
                for work in work_pages(aid,args.max_works_per_author):
                    d=work.get("publication_date")
                    if not d:continue
                    aff=author_affiliation(work,aid);topic=work.get("primary_topic") or {};field=topic.get("field") or {}
                    wid=(work.get("id") or "").rsplit("/",1)[-1]
                    wr.writerow({"event_id":f"{q}:openalex:{wid}","person_id":q,"event_type":"creation.scholar_work",
                      "event_date":d,"openalex_work_id":wid,"doi":work.get("doi") or "","title":work.get("title") or "",
                      "work_type":work.get("type") or "",**aff,
                      "primary_topic_id":(topic.get("id") or "").rsplit("/",1)[-1],"primary_topic_name":topic.get("display_name") or "",
                      "primary_field_id":(field.get("id") or "").rsplit("/",1)[-1],"primary_field_name":field.get("display_name") or "",
                      "source_id":"openalex","source_url":work.get("id") or "","identity_method":"wikidata_p10283_exact_openalex"})
                    events+=1;people.add(q)
                if (a.get("works_count") or 0)>args.max_works_per_author:truncated+=1
            except Exception as e:
                failed+=1;print(f"warning direct OpenAlex failed {q}/{aid}: {e!r}",flush=True)
            if n%50==0:print(f"direct_openalex={n}/{len(primary)} events={events}",flush=True)
    with gzip.open(outdir/"academic_authors_p10283.csv.gz","wt",encoding="utf-8",newline="") as aw:
        wr=csv.DictWriter(aw,fieldnames=afields);wr.writeheader();wr.writerows(authors)
    report={"input_qids":len(qids),"people_with_p10283":len(bridge),"single_openalex_id_people":len(primary),
            "verified_openalex_authors":len(authors),"people_with_scholarly_events":len(people),
            "scholarly_event_rows":events,"failed_people":failed,"authors_truncated_at_work_cap":truncated,
            "identity_method":"Wikidata P10283 exact OpenAlex author id; no fuzzy names"}
    (outdir/"academic_p10283.report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
