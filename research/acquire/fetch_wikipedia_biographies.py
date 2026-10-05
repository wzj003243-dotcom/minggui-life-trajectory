"""Fetch revision-pinned Wikipedia biography wikitext for a selected QID cohort.

Every record is pinned to a concrete revision id/timestamp and preserves the raw main-slot
wikitext as a research artifact. Downstream extraction converts wikitext to plaintext and
keeps revision/source provenance on every candidate event.

Current language preference: English, then Chinese.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

WD="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
SITES=("enwiki","zhwiki")
HOST={"enwiki":"https://en.wikipedia.org/w/api.php","zhwiki":"https://zh.wikipedia.org/w/api.php"}

def post_json(url,params,retries=10):
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req,timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504):
                raise
            retry=e.headers.get("Retry-After")
            try: delay=float(retry) if retry else min(120,max(8,2**a))+random.random()
            except: delay=min(120,max(8,2**a))+random.random()
            if a==retries-1: raise
            time.sleep(delay)
        except Exception:
            if a==retries-1: raise
            time.sleep(min(60,max(4,2**a))+random.random())

def read_people(path,id_column,limit):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or r.get("wikidata_id") or r.get("wikidata_code") or "").strip()
            if q.startswith("Q") and q[1:].isdigit():
                rows.append((q,r.get("sample_stratum",""),r.get("number_wiki_editions","")))
    rows=sorted(set(rows),key=lambda x:(x[1],int(x[0][1:])))
    return rows[:limit] if limit>0 else rows

def resolve_sitelinks(qids):
    result={}
    for i in range(0,len(qids),20):
        batch=qids[i:i+20]
        data=post_json(WD,{
          "action":"wbgetentities","format":"json","formatversion":"2","ids":"|".join(batch),
          "props":"sitelinks","sitefilter":"|".join(SITES),"maxlag":"5"
        })
        ents=data.get("entities",{})
        for q in batch:
            sl=ents.get(q,{}).get("sitelinks",{})
            for site in SITES:
                title=sl.get(site,{}).get("title")
                if title:
                    result[q]=(site,title)
                    break
        time.sleep(.35)
    return result

def revision_content(rev):
    slots=rev.get("slots") or {}
    main=slots.get("main") or {}
    return main.get("content") or rev.get("content") or rev.get("*") or ""

def fetch_site(site,pairs,batch_size=1):
    """pairs: [(qid,title)] -> revision-pinned records"""
    api=HOST[site];out=[];failed=0
    for i in range(0,len(pairs),batch_size):
        batch=pairs[i:i+batch_size]
        title_to_q={title:q for q,title in batch}
        try:
            data=post_json(api,{
              "action":"query","format":"json","formatversion":"2","redirects":"1",
              "titles":"|".join(title_to_q),
              "prop":"revisions",
              "rvprop":"ids|timestamp|content|sha1",
              "rvslots":"main",
              "rvlimit":"1",
              "maxlag":"5"
            })
        except Exception as e:
            print(f"warning: biography batch failed site={site} i={i}: {e!r}",flush=True)
            failed+=len(batch)
            continue
        normalized={x["from"]:x["to"] for x in data.get("query",{}).get("normalized",[])}
        redirects={x["from"]:x["to"] for x in data.get("query",{}).get("redirects",[])}
        def source_q(title):
            for original,q in title_to_q.items():
                x=normalized.get(original,original);x=redirects.get(x,x)
                if x==title:return q
            return title_to_q.get(title)
        for page in data.get("query",{}).get("pages",[]):
            if page.get("missing"):continue
            q=source_q(page.get("title"))
            if not q:continue
            rev=(page.get("revisions") or [{}])[0]
            raw=revision_content(rev)
            if not raw.strip():continue
            out.append({
              "person_id":q,"site":site,"language":"en" if site=="enwiki" else "zh",
              "title":page.get("title"),"pageid":page.get("pageid"),
              "revision_id":rev.get("revid"),"revision_parent_id":rev.get("parentid"),
              "revision_timestamp":rev.get("timestamp"),"revision_sha1":rev.get("sha1"),
              "wikitext":raw,"content_chars":len(raw),
              "license":"CC BY-SA","source_url":f"https://{site[:-4]}.wikipedia.org/?curid={page.get('pageid')}&oldid={rev.get('revid')}"
            })
        if (i//batch_size+1)%20==0:
            print(f"{site}: fetched={min(i+batch_size,len(pairs))}/{len(pairs)} records={len(out)}",flush=True)
        time.sleep(.25)
    return out,failed

def main():
    ap=argparse.ArgumentParser();ap.add_argument("cohort");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--limit",type=int,default=2000)
    ap.add_argument("--sitelink-map",default="")
    args=ap.parse_args()
    people=read_people(Path(args.cohort),args.id_column,args.limit);qids=[x[0] for x in people]
    if args.sitelink_map:
        allowed=set(qids);links={}
        with gzip.open(args.sitelink_map,"rt",encoding="utf-8",newline="") as mf:
            for row in csv.DictReader(mf):
                q=(row.get("wikidata_id") or "").strip()
                if q in allowed and row.get("site") and row.get("title"):
                    links[q]=(row["site"],row["title"])
    else:
        links=resolve_sitelinks(qids)
    by_site=defaultdict(list)
    for q,(site,title) in links.items():by_site[site].append((q,title))
    records=[];failed=0
    for site,pairs in by_site.items():
        got,bad=fetch_site(site,sorted(pairs))
        records.extend(got);failed+=bad
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8") as w:
        for r in records:w.write(json.dumps(r,ensure_ascii=False)+"\n")
    report={
      "requested_people":len(qids),"resolved_sitelinks":len(links),
      "biographies_fetched":len(records),"failed_fetch_qids":failed,
      "site_counts":{s:len(v) for s,v in by_site.items()},
      "content_chars_total":sum(r["content_chars"] for r in records),
      "raw_text_license":"CC BY-SA","content_mode":"revision main-slot wikitext"
    }
    report_path=out.with_name(out.name[:-10]+".report.json" if out.name.endswith(".jsonl.gz") else out.stem+".report.json")
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
