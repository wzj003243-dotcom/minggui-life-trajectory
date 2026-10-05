from __future__ import annotations
import json,sys,urllib.parse,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from research.acquire.fetch_openalex_academic_events import wikidata_orcids
from research.acquire.fetch_musicbrainz_events import wikidata_musicbrainz

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (diagnostic)"
QIDS=["Q483086","Q57546786"]

params={"action":"wbgetentities","format":"json","formatversion":"2","ids":"|".join(QIDS),"props":"claims"}
data=urllib.parse.urlencode(params).encode()
req=urllib.request.Request(API,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
with urllib.request.urlopen(req,timeout=60) as r:
    payload=json.load(r)

print("entities_type",type(payload.get("entities")).__name__)
print("entities_keys",list(payload.get("entities",{}))[:10])
for q in QIDS:
    e=(payload.get("entities") or {}).get(q,{})
    vals={}
    for prop in ("P496","P434"):
        vals[prop]=[
          c.get("mainsnak",{}).get("datavalue",{}).get("value")
          for c in e.get("claims",{}).get(prop,[])
        ]
    print(q,json.dumps(vals,ensure_ascii=False))

print("academic_single",{k:sorted(v) for k,v in wikidata_orcids(["Q483086"],batch_size=1).items()})
print("academic_pair",{k:sorted(v) for k,v in wikidata_orcids(QIDS,batch_size=2).items()})
print("music_pair",{k:sorted(v) for k,v in wikidata_musicbrainz(QIDS,batch_size=2).items()})

print("ORCID_RE", __import__("research.acquire.fetch_openalex_academic_events", fromlist=["ORCID_RE"]).ORCID_RE.pattern)
e=(payload.get("entities") or {}).get("Q483086",{})
for claim in e.get("claims",{}).get("P496",[]):
    v=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
    from research.acquire.fetch_openalex_academic_events import ORCID_RE
    print("claim_debug", repr(claim.get("rank")), repr(v), bool(isinstance(v,str)), bool(ORCID_RE.match(v if isinstance(v,str) else "")))

from research.acquire.fetch_openalex_academic_events import resolve_openalex
from research.acquire.fetch_musicbrainz_events import wikidata_musicbrainz
from research.acquire.fetch_wikipedia_biographies import resolve_sitelinks, fetch_site

oa,_amb=resolve_openalex({"0000-0003-3206-1556":{"Q483086"}},batch_size=1)
print("openalex_exact", {k: (v.get("id"),v.get("display_name")) for k,v in oa.items()})

music_qids=["Q26876"]
print("music_raw", {k:sorted(v) for k,v in wikidata_musicbrainz(music_qids,batch_size=1).items()})

links=resolve_sitelinks(["Q42"])
print("wiki_links",links)
if "Q42" in links:
    site,title=links["Q42"]
    rows,bad=fetch_site(site,[("Q42",title)],batch_size=1)
    print("wiki_revision_probe", {"rows":len(rows),"failed":bad,"chars":(rows[0]["content_chars"] if rows else 0),"revision_id":(rows[0]["revision_id"] if rows else None)})
