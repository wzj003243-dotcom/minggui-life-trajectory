"""Extract the BHHT records linked to Pantheon into a compact, high-quality cohort."""
from __future__ import annotations
import csv,gzip,sys
from pathlib import Path

FIELDS=[
  "wikidata_code","name","birth","death","gender","level1_main_occ","level2_main_occ","level3_main_occ",
  "un_region","un_subregion","number_wiki_editions","non_missing_score","ranking_visib_5criteria","pantheon_1"
]

def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: build_pantheon_linked_cohort.py cross-verified-database.csv.gz [output]")
    src=Path(sys.argv[1])
    out=Path(sys.argv[2] if len(sys.argv)>2 else "data/processed/pantheon_linked_bhht.csv.gz")
    out.parent.mkdir(parents=True,exist_ok=True)
    n=0
    with gzip.open(src,"rt",encoding="latin-1",newline="") as f, gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f)
        writer=csv.DictWriter(w,fieldnames=FIELDS)
        writer.writeheader()
        for row in r:
            if row.get("pantheon_1") not in ("1","1.0"):
                continue
            writer.writerow({k:row.get(k,"") for k in FIELDS})
            n+=1
    print(f"wrote {n:,} Pantheon-linked BHHT people -> {out}")

if __name__=="__main__": main()
