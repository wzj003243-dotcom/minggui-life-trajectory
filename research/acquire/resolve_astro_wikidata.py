"""Resolve Astro-Databank Wikipedia links to Wikidata QIDs via the official MediaWiki API.

Input: normalized astro_public_births.csv.gz
Output: adb_wikidata_links.csv.gz

The resolver groups pages by Wikipedia language/host and asks pageprops for wikibase_item.
It does not scrape article HTML.
"""
from __future__ import annotations
import argparse, csv, gzip, json, random, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from pathlib import Path

UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

def parse_wiki(url: str):
    if not url: return None
    try:
        u=urllib.parse.urlparse(url)
        host=u.netloc.lower()
        if not host.endswith(".wikipedia.org"): return None
        if not u.path.startswith("/wiki/"): return None
        title=urllib.parse.unquote(u.path[len("/wiki/"):]).replace("_"," ")
        if not title: return None
        return host,title
    except Exception:
        return None

def query(host: str, titles: list[str], retries=7):
    endpoint=f"https://{host}/w/api.php"
    params={
      "action":"query","format":"json","formatversion":"2","redirects":"1","maxlag":"5",
      "prop":"pageprops","ppprop":"wikibase_item","titles":"|".join(titles)
    }
    body=urllib.parse.urlencode(params).encode()
    for attempt in range(retries):
        req=urllib.request.Request(endpoint,data=body,headers={
          "User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"
        })
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            retry=e.headers.get("Retry-After")
            delay=float(retry) if retry and retry.isdigit() else min(45,2**attempt+random.random())
            if e.code not in (429,500,502,503,504) or attempt==retries-1: raise
            time.sleep(delay)
        except Exception:
            if attempt==retries-1: raise
            time.sleep(min(45,2**attempt+random.random()))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--batch-size",type=int,default=35)
    ap.add_argument("--sleep",type=float,default=.6)
    args=ap.parse_args()
    grouped=defaultdict(list)
    bad=[]
    with gzip.open(args.input,"rt",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            parsed=parse_wiki(row.get("wikipedia_url") or "")
            if parsed: grouped[parsed[0]].append((row["adb_id"],parsed[1],row["wikipedia_url"],row.get("rodden_rating")))
            elif row.get("wikipedia_url"): bad.append(row["adb_id"])

    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    fields=["adb_id","rodden_rating","wikipedia_host","wikipedia_title","wikipedia_url","wikidata_id","resolution_status","error"]
    resolved=0; requested=0; failed=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields); wr.writeheader()
        for host,rows in grouped.items():
            for start in range(0,len(rows),args.batch_size):
                batch=rows[start:start+args.batch_size]
                requested+=len(batch)
                try:
                    data=query(host,[x[1] for x in batch])
                    pages=data.get("query",{}).get("pages",[])
                    # API can normalize/redirect titles, so match by requested title after redirects where possible;
                    # for ambiguous misses, fall back to page-title lookup.
                    by_title={p.get("title"):p for p in pages}
                    # redirects map from original to canonical
                    redirects={x.get("from"):x.get("to") for x in data.get("query",{}).get("redirects",[])}
                    normalized={x.get("from"):x.get("to") for x in data.get("query",{}).get("normalized",[])}
                    for adb,title,url,rr in batch:
                        canonical=redirects.get(normalized.get(title,title),normalized.get(title,title))
                        page=by_title.get(canonical) or by_title.get(title)
                        qid=(page or {}).get("pageprops",{}).get("wikibase_item")
                        if qid: resolved+=1
                        wr.writerow({
                          "adb_id":adb,"rodden_rating":rr,"wikipedia_host":host,
                          "wikipedia_title":title,"wikipedia_url":url,"wikidata_id":qid,
                          "resolution_status":"resolved" if qid else "no_wikibase_item","error":""
                        })
                except Exception as e:
                    failed+=len(batch)
                    for adb,title,url,rr in batch:
                        wr.writerow({
                          "adb_id":adb,"rodden_rating":rr,"wikipedia_host":host,
                          "wikipedia_title":title,"wikipedia_url":url,"wikidata_id":"",
                          "resolution_status":"request_failed","error":repr(e)[:240]
                        })
                w.flush()
                time.sleep(args.sleep)
    report={
      "wikipedia_links_requested":requested,
      "resolved_wikidata_ids":resolved,
      "resolution_rate":resolved/requested if requested else 0,
      "request_failed":failed,
      "unparseable_wikipedia_links":len(bad),
      "languages_or_hosts":len(grouped)
    }
    rp=out.with_suffix("").with_suffix(".report.json")
    rp.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
