"""Standardize timed-core birth geography using Wikidata P19 -> place P17.

This is a geography-control table, not a historical-nationality table.
- Person identity comes from the already verified timed core.
- Birthplace claims are preserved with ambiguity status.
- Present-day country is resolved from the place's P17, optionally through P131 parents.
- Astro place/country/coordinates remain alongside Wikidata geography for disagreement audits.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math,random,time,urllib.parse,urllib.request,urllib.error
from collections import defaultdict
from pathlib import Path

API="https://www.wikidata.org/w/api.php"
UA="MingGuiLifeTrajectory/0.1 (public research; github.com/wzj003243-dotcom/minggui-life-trajectory)"

def get_entities(qids,props="labels|claims",retries=8):
    if not qids:return {}
    params={
      "action":"wbgetentities","format":"json","formatversion":"2","maxlag":"5",
      "ids":"|".join(qids),"props":props,"languages":"en"
    }
    data=urllib.parse.urlencode(params).encode()
    for a in range(retries):
        req=urllib.request.Request(API,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req,timeout=90) as r:return json.load(r).get("entities",{})
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

def claim_items(ent,prop):
    preferred=[];normal=[]
    for c in ent.get("claims",{}).get(prop,[]):
        if c.get("rank")=="deprecated":continue
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and v.get("entity-type")=="item" and v.get("id"):
            (preferred if c.get("rank")=="preferred" else normal).append(v["id"])
    vals=preferred or normal
    return sorted(set(vals)),("preferred" if preferred else ("normal" if normal else "missing"))

def coordinate(ent):
    for c in ent.get("claims",{}).get("P625",[]):
        if c.get("rank")=="deprecated":continue
        v=c.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "latitude" in v and "longitude" in v:
            return v.get("latitude"),v.get("longitude")
    return None,None

def label(ent):
    return ent.get("labels",{}).get("en",{}).get("value","")

def haversine(lat1,lon1,lat2,lon2):
    try:
        p1,p2=math.radians(float(lat1)),math.radians(float(lat2))
        dp=math.radians(float(lat2)-float(lat1));dl=math.radians(float(lon2)-float(lon1))
    except:return None
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(a)))

def batches(xs,n=40):
    xs=list(xs)
    for i in range(0,len(xs),n):yield xs[i:i+n]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("core");ap.add_argument("output");args=ap.parse_args()
    with gzip.open(args.core,"rt",encoding="utf-8",newline="") as f:
        core=list(csv.DictReader(f))
    qids=[r["wikidata_id"] for r in core if (r.get("wikidata_id") or "").startswith("Q")]

    people={}
    for b in batches(qids):
        people.update(get_entities(b,"claims"))
        time.sleep(.15)

    person_places={};place_ids=set()
    for q in qids:
        vals,rank=claim_items(people.get(q,{}),"P19")
        person_places[q]=(vals,rank);place_ids.update(vals)

    places={}
    for b in batches(sorted(place_ids)):
        places.update(get_entities(b))
        time.sleep(.15)

    # Resolve P17 directly; for missing P17, walk administrative parents up to three levels.
    place_country={};place_parent={};country_ids=set();frontier=set()
    for pq,e in places.items():
        cs,_=claim_items(e,"P17");ps,_=claim_items(e,"P131")
        place_country[pq]=cs;place_parent[pq]=ps
        country_ids.update(cs)
        if not cs:frontier.update(ps)

    ancestors={}
    for _depth in range(3):
        unknown=[q for q in frontier if q not in ancestors]
        if not unknown:break
        for b in batches(sorted(unknown)):
            ancestors.update(get_entities(b))
            time.sleep(.15)
        new_frontier=set()
        for q in unknown:
            e=ancestors.get(q,{})
            cs,_=claim_items(e,"P17");ps,_=claim_items(e,"P131")
            country_ids.update(cs)
            if not cs:new_frontier.update(ps)
        frontier=new_frontier

    countries={}
    for b in batches(sorted(country_ids)):
        countries.update(get_entities(b,"labels"))
        time.sleep(.15)

    def inherited_country(pq):
        direct=place_country.get(pq,[])
        if direct:return direct[0],"direct"
        seen=set();queue=[(x,1) for x in place_parent.get(pq,[])]
        while queue:
            q,depth=queue.pop(0)
            if q in seen or depth>3:continue
            seen.add(q);e=ancestors.get(q,{})
            cs,_=claim_items(e,"P17")
            if cs:return cs[0],f"admin_parent_depth_{depth}"
            ps,_=claim_items(e,"P131")
            queue.extend((x,depth+1) for x in ps)
        return None,"missing"

    fields=[
      "person_id","birthplace_qid","birthplace_label_en","p19_rank","p19_candidate_count",
      "wikidata_latitude","wikidata_longitude","present_day_country_qid","present_day_country_label_en",
      "country_resolution","admin_parent_qids","timezone_qids",
      "astro_place","astro_country_raw","astro_latitude","astro_longitude","coordinate_delta_km",
      "geo_primary_eligible","country_semantics"
    ]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    counts=defaultdict(int);deltas=[]
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for row in core:
            q=row["wikidata_id"];vals,rank=person_places.get(q,([], "missing"))
            pq=vals[0] if len(vals)==1 else ""
            e=places.get(pq,{}) if pq else {}
            lat,lon=coordinate(e)
            cq,method=inherited_country(pq) if pq else (None,"missing")
            parents,_=claim_items(e,"P131") if e else ([], "missing")
            tz,_=claim_items(e,"P421") if e else ([], "missing")
            delta=haversine(row.get("birth_latitude"),row.get("birth_longitude"),lat,lon) if lat is not None else None
            eligible=bool(pq and cq and lat is not None and lon is not None and len(vals)==1)
            if eligible:counts["eligible"]+=1
            if len(vals)>1:counts["ambiguous_p19"]+=1
            if cq:counts["country_resolved"]+=1
            if delta is not None:deltas.append(delta)
            wr.writerow({
              "person_id":q,"birthplace_qid":pq,"birthplace_label_en":label(e),"p19_rank":rank,
              "p19_candidate_count":len(vals),"wikidata_latitude":"" if lat is None else lat,
              "wikidata_longitude":"" if lon is None else lon,"present_day_country_qid":cq or "",
              "present_day_country_label_en":label(countries.get(cq,{})) if cq else "",
              "country_resolution":method,"admin_parent_qids":"|".join(parents),"timezone_qids":"|".join(tz),
              "astro_place":row.get("birth_place",""),"astro_country_raw":row.get("birth_country",""),
              "astro_latitude":row.get("birth_latitude",""),"astro_longitude":row.get("birth_longitude",""),
              "coordinate_delta_km":"" if delta is None else round(delta,3),
              "geo_primary_eligible":str(eligible).lower(),
              "country_semantics":"present-day jurisdiction resolved from Wikidata place P17/P131; not historical nationality"
            })
    deltas.sort()
    def qv(fr):
        return None if not deltas else deltas[min(len(deltas)-1,round((len(deltas)-1)*fr))]
    report={
      "core_people":len(core),"people_with_p19":sum(bool(v[0]) for v in person_places.values()),
      "geo_primary_eligible":counts["eligible"],"ambiguous_p19":counts["ambiguous_p19"],
      "country_resolved":counts["country_resolved"],
      "coordinate_delta_km":{"median":qv(.5),"p90":qv(.9),"p99":qv(.99)},
      "country_semantics":"present-day P17/P131 geography control only; not historical nationality/citizenship"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
