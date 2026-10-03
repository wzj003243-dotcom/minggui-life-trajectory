"""Fetch revision-pinned Wikipedia biography plaintext for a selected QID cohort.

The raw extracts are research artifacts, not committed to git. Each record keeps page/revision
metadata so every derived timeline candidate can be traced back to a specific CC BY-SA source.

Current language preference: English, then Chinese. The pipeline is intentionally extensible
to multilingual sources so English Wikipedia is not silently treated as universal ground truth.
"""
from __future__ import annotations
import argparse,csv,gzip,json,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

WD="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"
SITES=("enwiki","zhwiki")
HOST={"enwiki":"https://en.wikipedia.org/w/api.php","zhwiki":"https://zh.wikipedia.org/w/api.php"}

def post_json(url,params,retries=9):
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or a==retries-1:raise
            retry=e.headers.get("Retry-After")
            if retry:
                try:delay=float(retry)
                except:delay=10
            elif e.code==429:
                delay=min(120,10*(2**a))+random.random()
            else:
                delay=min(45,2**a)+random.random()
            time.sleep(delay)
        except Exception:
            if a==retries-1:raise
            time.sleep(min(30,2**a)+random.random())

def read_people(path,id_column,limit):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get(id_column) or "").strip()
            if q.startswith("Q") and q[1:].isdigit():rows.append((q,r.get("sample_stratum",""),r.get("number_wiki_editions","")))
    # stable, diverse-ish ordering: stratum then QID; caller can cap
    rows=sorted(set(rows),key=lambda x:(x[1],int(x[0][1:])))
    return rows[:limit] if limit>0 else rows

def resolve_sitelinks(qids):
    result={}
    for i in range(0,len(qids),20):
        batch=qids[i:i+20]
        data=post_json(WD,{"action":"wbgetentities","format":"json","formatversion":"2","ids":"|".join(batch),
                           "props":"sitelinks","sitefilter":"|".join(SITES),"maxlag":"5"})
        ents=data.get("entities",{})
        for q in batch:
            sl=ents.get(q,{}).get("sitelinks",{})
            chosen=None
            for site in SITES:
                if site in sl:
                    chosen=(site,sl[site].get("title"));break
            if chosen and chosen[1]:result[q]=chosen
        time.sleep(.35)
    return result

def fetch_site(site,pairs,batch_size=6):
    """pairs: [(qid,title)] -> records"""
    api=HOST[site];out=[]
    for i in range(0,len(pairs),batch_size):
        batch=pairs[i:i+batch_size];title_to_q={title:q for q,title in batch}
        data=post_json(api,{
          "action":"query","format":"json","formatversion":"2","redirects":"1",
          "titles":"|".join(title_to_q),"prop":"extracts|revisions","explaintext":"1",
          "exsectionformat":"plain","rvprop":"ids|timestamp","rvlimit":"1","maxlag":"5"
        })
        normalized={x["from"]:x["to"] for x in data.get("query",{}).get("normalized",[])}
        redirects={x["from"]:x["to"] for x in data.get("query",{}).get("redirects",[])}
        def source_q(title):
            # Resolve response title back through redirects/normalization.
            for original,q in title_to_q.items():
                x=normalized.get(original,original);x=redirects.get(x,x)
                if x==title:return q
            return title_to_q.get(title)
        for page in data.get("query",{}).get("pages",[]):
            if page.get("missing"):continue
            q=source_q(page.get("title"))
            if not q:continue
            rev=(page.get("revisions") or [{}])[0]
            extract=page.get("extract") or ""
            if not extract.strip():continue
            out.append({
              "person_id":q,"site":site,"language":"en" if site=="enwiki" else "zh",
              "title":page.get("title"),"pageid":page.get("pageid"),
              "revision_id":rev.get("revid"),"revision_parent_id":rev.get("parentid"),
              "revision_timestamp":rev.get("timestamp"),"extract":extract,
              "license":"CC BY-SA","source_url":f"https://{site[:-4]}.wikipedia.org/?curid={page.get('pageid')}"
            })
        time.sleep(.30)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("cohort");ap.add_argument("output")
    ap.add_argument("--id-column",default="wikidata_id");ap.add_argument("--limit",type=int,default=2000)
    args=ap.parse_args()
    people=read_people(Path(args.cohort),args.id_column,args.limit);qids=[x[0] for x in people]
    links=resolve_sitelinks(qids)
    by_site=defaultdict(list)
    for q,(site,title) in links.items():by_site[site].append((q,title))
    records=[]
    for site,pairs in by_site.items():records.extend(fetch_site(site,sorted(pairs)))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8") as w:
        for r in records:w.write(json.dumps(r,ensure_ascii=False)+"\n")
    report={"requested_people":len(qids),"resolved_sitelinks":len(links),"biographies_fetched":len(records),
            "site_counts":{s:len(v) for s,v in by_site.items()},"raw_text_license":"CC BY-SA"}
    out.with_name(out.name[:-10]+".report.json" if out.name.endswith(".jsonl.gz") else out.stem+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
