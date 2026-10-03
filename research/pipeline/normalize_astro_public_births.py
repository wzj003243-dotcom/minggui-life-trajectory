"""Normalize only Astro-Databank public_data birth fields from the free C sample.

Do NOT export research_data. Do NOT copy sourcenotes/shortbiography here.
This derived table is for internal research and aggregate model evaluation.
"""
from __future__ import annotations
import csv,json,sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path

PRIMARY={"AA","A","B"}

def text(node,path):
    x=node.find(path)
    return (x.text or "").strip() if x is not None else ""

def main():
    src=Path(sys.argv[1])
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/astro_public_births.ndjson")
    out.parent.mkdir(parents=True,exist_ok=True)
    n=primary=0
    with zipfile.ZipFile(src) as z, z.open(z.namelist()[0]) as xf, out.open("w",encoding="utf-8") as w:
        for _,e in ET.iterparse(xf,events=("end",)):
            if e.tag.split("}")[-1]!="adb_entry":continue
            pd=e.find("public_data");bd=e.find("./public_data/bdata")
            if pd is None or bd is None:e.clear();continue
            d=bd.find("sbdate");t=bd.find("sbtime");pl=bd.find("place");co=bd.find("country");rrn=pd.find("roddenrating")
            if d is None or t is None:e.clear();continue
            rr=(rrn.text or "").strip() if rrn is not None else ""
            row={
              "adb_id":e.attrib.get("adb_id"),
              "name":text(e,"./public_data/name"),
              "gender":text(e,"./public_data/gender"),
              "rodden_rating":rr,
              "primary_timed_cohort":rr in PRIMARY,
              "calendar":d.attrib.get("ccalendar"),
              "year":int(d.attrib["iyear"]),"month":int(d.attrib["imonth"]),"day":int(d.attrib["iday"]),
              "local_time":(t.text or "").strip(),
              "time_type":t.attrib.get("ctimetype"),
              "time_type_label":t.attrib.get("stimetype"),
              "meridian":t.attrib.get("stmerid"),
              "zone_abbr":t.attrib.get("sznabbr"),
              "jd_ut":t.attrib.get("jd_ut"),
              "place":(pl.text or "").strip() if pl is not None else None,
              "latitude_raw":pl.attrib.get("slati") if pl is not None else None,
              "longitude_raw":pl.attrib.get("slong") if pl is not None else None,
              "country":(co.text or "").strip() if co is not None else None
            }
            w.write(json.dumps(row,ensure_ascii=False)+"\n")
            n+=1;primary+=rr in PRIMARY
            e.clear()
    print(f"normalized {n:,}; primary AA/A/B={primary:,} -> {out}")

if __name__=="__main__":main()
