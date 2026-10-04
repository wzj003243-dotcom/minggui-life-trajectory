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
