"""Profile the three acquired public datasets without loading BHHT fully into memory."""
from __future__ import annotations
import csv,gzip,json,statistics,sys,zipfile,xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

def profile(root:Path):
    # Pantheon
    with (root/"pantheon.tsv").open(encoding="utf-8",newline="") as f:
        r=csv.DictReader(f,delimiter="\t"); p_rows=0;p_occ=Counter();p_dom=Counter();p_coord=0;years=[]
        for x in r:
            p_rows+=1;p_occ[x["occupation"]]+=1;p_dom[x["domain"]]+=1
            if x.get("LAT") and x.get("LON"):p_coord+=1
            try:years.append(int(float(x["birthyear"])))
            except:pass

    # BHHT
    with gzip.open(root/"cross-verified-database.csv.gz","rt",encoding="latin-1",newline="") as f:
        r=csv.DictReader(f); b_rows=qids=births=pantheon=0;b_occ=Counter();regions=Counter()
        for x in r:
            b_rows+=1
            qids+=bool(x.get("wikidata_code"))
            births+=bool(x.get("birth"))
            pantheon+=x.get("pantheon_1") in ("1","1.0")
            b_occ[x.get("level1_main_occ","")]+=1;regions[x.get("un_region","")]+=1

    # Astro free C sample
    rr=Counter();cal=Counter();timetype=Counter();entries=0;wiki=0
    with zipfile.ZipFile(root/"c_sample.zip") as z, z.open(z.namelist()[0]) as xf:
        for _,elem in ET.iterparse(xf,events=("end",)):
            if elem.tag.split("}")[-1]!="adb_entry":continue
            entries+=1
            rn=elem.find("./public_data/roddenrating")
            if rn is not None:rr[(rn.text or "").strip()]+=1
            bd=elem.find("./public_data/bdata")
            if bd is not None:
                d=bd.find("sbdate");t=bd.find("sbtime")
                if d is not None:cal[d.attrib.get("ccalendar","")]+=1
                if t is not None:timetype[t.attrib.get("ctimetype","")]+=1
            if elem.find("./text_data/wikipedia_link") is not None:wiki+=1
            elem.clear()

    return {
      "pantheon":{"rows":p_rows,"birth_year_range":[min(years),max(years)],"coordinates":p_coord,"top_occupations":p_occ.most_common(20),"domains":p_dom.most_common()},
      "bhht":{"rows":b_rows,"wikidata_qids":qids,"birth_year_nonmissing":births,"pantheon_linked":pantheon,"level1_occupations":b_occ.most_common(),"regions":regions.most_common()},
      "astro_free_c_sample":{"rows":entries,"rodden":rr.most_common(),"calendars":cal.most_common(),"time_types":timetype.most_common(),"wikipedia_links":wiki}
    }

if __name__=="__main__":
    root=Path(sys.argv[1] if len(sys.argv)>1 else "data/raw/acquired")
    out=profile(root)
    if len(sys.argv)>2: Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
