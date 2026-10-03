"""Probe Wikidata identifier claims for known QIDs; diagnostic only."""
from __future__ import annotations
import json,urllib.parse,urllib.request

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (diagnostic)"
QIDS=["Q483086","Q57546786"]
params={"action":"wbgetentities","format":"json","formatversion":"2","ids":"|".join(QIDS),"props":"claims"}
data=urllib.parse.urlencode(params).encode()
req=urllib.request.Request(API,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
with urllib.request.urlopen(req,timeout=60) as r:
    payload=json.load(r)
print("entities_type",type(payload.get("entities")).__name__)
print("entities_keys",list(payload.get("entities",{}))[:10] if isinstance(payload.get("entities"),dict) else "not-dict")
for q in QIDS:
    e=(payload.get("entities") or {}).get(q,{}) if isinstance(payload.get("entities"),dict) else {}
    vals={}
    for prop in ("P496","P434"):
        vals[prop]=[
          c.get("mainsnak",{}).get("datavalue",{}).get("value")
          for c in e.get("claims",{}).get(prop,[])
        ]
    print(q,json.dumps(vals,ensure_ascii=False))

import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[2]))\nfrom research.acquire.fetch_openalex_academic_events import wikidata_orcids
print("academic_single", {k: sorted(v) for k,v in wikidata_orcids(["Q483086"],batch_size=1).items()})
