"""Normalize acquired public datasets into compact, training-friendly files.

Raw files remain outside git. This script is intentionally streaming for BHHT (~2.29M rows).

Usage:
  python research/normalize/public_cohorts.py data/raw/acquired data/processed/public

Outputs:
  pantheon_core.csv.gz
  bhht_core.csv.gz
  astro_public_births.csv.gz
  public_cohort_profile.json
"""
from __future__ import annotations
import csv, gzip, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

def open_csv_read(path: Path, encoding="utf-8"):
    if path.suffix == ".gz":
        return gzip.open(path,"rt",encoding=encoding,newline="",errors="replace")
    return path.open("r",encoding=encoding,newline="",errors="replace")

def open_csv_write(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    return gzip.open(path,"wt",encoding="utf-8",newline="") if path.suffix==".gz" else path.open("w",encoding="utf-8",newline="")

def normalize_pantheon(raw: Path, out: Path):
    keep=["en_curid","name","numlangs","birthcity","birthstate","countryName","countryCode","countryCode3","LAT","LON","continentName","birthyear","gender","occupation","industry","domain","HPI"]
    rows=0; valid_year=0; occ=Counter()
    with open_csv_read(raw) as f, open_csv_write(out) as w:
        r=csv.DictReader(f,delimiter="\t")
        wr=csv.DictWriter(w,fieldnames=keep); wr.writeheader()
        for row in r:
            rows+=1
            y=(row.get("birthyear") or "").strip()
            try: int(y); valid_year+=1
            except: pass
            if row.get("occupation"): occ[row["occupation"]]+=1
            wr.writerow({k:row.get(k) for k in keep})
    return {"rows":rows,"valid_numeric_birth_year":valid_year,"top_occupations":dict(occ.most_common(20))}

def normalize_bhht(raw: Path, out: Path):
    keep=[
      "wikidata_code","birth","death","gender","level1_main_occ","level2_main_occ","level2_second_occ",
      "level3_main_occ","un_region","un_subregion","number_wiki_editions","non_missing_score",
      "ranking_visib_5criteria","pantheon_1","bplo1","bpla1","group_wikipedia_editions"
    ]
    rows=0; birth_present=0; coords=0; pantheon_overlap=0; occ=Counter(); genders=Counter()
    with open_csv_read(raw,encoding="latin1") as f, open_csv_write(out) as w:
        r=csv.DictReader(f)
        wr=csv.DictWriter(w,fieldnames=keep); wr.writeheader()
        for row in r:
            rows+=1
            if (row.get("birth") or "").strip(): birth_present+=1
            if (row.get("bplo1") or "").strip() and (row.get("bpla1") or "").strip(): coords+=1
            if (row.get("pantheon_1") or "").strip()=="1": pantheon_overlap+=1
            if row.get("level1_main_occ"): occ[row["level1_main_occ"]]+=1
            if row.get("gender"): genders[row["gender"]]+=1
            wr.writerow({k:row.get(k) for k in keep})
    return {
      "rows":rows,"birth_present":birth_present,"coordinate_rows":coords,"pantheon_overlap":pantheon_overlap,
      "level1_occupation_counts":dict(occ),"gender_counts":dict(genders)
    }

def parse_coord(raw: str | None):
    if not raw: return None
    m=re.fullmatch(r"(\d+)([nsew])(\d+)?",raw.strip(),re.I)
    if not m: return None
    deg=int(m.group(1)); mins=int(m.group(3) or 0); x=deg+mins/60
    return -x if m.group(2).lower() in ("s","w") else x

def child_text(parent, tag):
    x=parent.find(tag) if parent is not None else None
    return (x.text or "").strip() if x is not None and x.text else None

def normalize_astro(raw_zip: Path, out: Path):
    fields=[
      "adb_id","name","gender","rodden_rating","birth_date","birth_time_local","calendar","time_type","time_type_code",
      "meridian","jd_ut","timezone_abbr","place","country","latitude","longitude","wikipedia_url","adb_url"
    ]
    ratings=Counter(); rows=0; wikipedia=0
    with zipfile.ZipFile(raw_zip) as z:
        xml_name=z.namelist()[0]
        with open_csv_write(out) as w, z.open(xml_name) as fh:
            wr=csv.DictWriter(w,fieldnames=fields); wr.writeheader()
            for _,entry in ET.iterparse(fh,events=("end",)):
                if entry.tag!="adb_entry": continue
                rows+=1
                pub=entry.find("public_data"); txt=entry.find("text_data")
                if pub is None: entry.clear(); continue
                rr=child_text(pub,"roddenrating"); ratings[rr]+=1
                b=pub.find("bdata"); sbdate=b.find("sbdate") if b is not None else None
                sbtime=b.find("sbtime") if b is not None else None
                place=b.find("place") if b is not None else None
                country=b.find("country") if b is not None else None
                wiki=child_text(txt,"wikipedia_link") if txt is not None else None
                if wiki: wikipedia+=1
                wr.writerow({
                  "adb_id":entry.attrib.get("adb_id"),
                  "name":child_text(pub,"name"),
                  "gender":child_text(pub,"gender"),
                  "rodden_rating":rr,
                  "birth_date":(sbdate.text or "").strip() if sbdate is not None and sbdate.text else None,
                  "birth_time_local":(sbtime.text or "").strip() if sbtime is not None and sbtime.text else None,
                  "calendar":sbdate.attrib.get("ccalendar") if sbdate is not None else None,
                  "time_type":sbtime.attrib.get("stimetype") if sbtime is not None else None,
                  "time_type_code":sbtime.attrib.get("ctimetype") if sbtime is not None else None,
                  "meridian":sbtime.attrib.get("stmerid") if sbtime is not None else None,
                  "jd_ut":sbtime.attrib.get("jd_ut") if sbtime is not None else None,
                  "timezone_abbr":sbtime.attrib.get("sznabbr") if sbtime is not None else None,
                  "place":(place.text or "").strip() if place is not None and place.text else None,
                  "country":(country.text or "").strip() if country is not None and country.text else None,
                  "latitude":parse_coord(place.attrib.get("slati")) if place is not None else None,
                  "longitude":parse_coord(place.attrib.get("slong")) if place is not None else None,
                  "wikipedia_url":wiki,
                  "adb_url":child_text(txt,"adb_link") if txt is not None else None
                })
                entry.clear()
    return {"rows":rows,"wikipedia_links":wikipedia,"rodden_rating_counts":dict(ratings),"primary_AA_A_B":sum(ratings[x] for x in ("AA","A","B"))}

def main():
    raw=Path(sys.argv[1] if len(sys.argv)>1 else "data/raw/acquired")
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/public")
    out.mkdir(parents=True,exist_ok=True)
    profile={
      "pantheon":normalize_pantheon(raw/"pantheon.tsv",out/"pantheon_core.csv.gz"),
      "bhht":normalize_bhht(raw/"cross-verified-database.csv.gz",out/"bhht_core.csv.gz"),
      "astro":normalize_astro(raw/"c_sample.zip",out/"astro_public_births.csv.gz")
    }
    (out/"public_cohort_profile.json").write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(profile,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
