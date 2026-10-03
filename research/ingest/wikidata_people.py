"""Minimal Wikidata cohort fetcher.
Run with internet access. Writes NDJSON; do not treat it as a finished biography timeline.
"""
import json, urllib.parse, urllib.request
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = r'''
SELECT ?person ?personLabel ?dob ?pob ?pobLabel ?occupation ?occupationLabel WHERE {
  ?person wdt:P31 wd:Q5; wdt:P569 ?dob; wdt:P106 ?occupation.
  OPTIONAL { ?person wdt:P19 ?pob. }
  FILTER(YEAR(?dob) >= 1800)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,zh". }
}
LIMIT 5000
'''

def fetch():
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY, "format":"json"})
    req = urllib.request.Request(url, headers={"User-Agent":"MingGuiResearch/0.1 (public research project)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["results"]["bindings"]

def main():
    out = Path("data/raw/wikidata_people.ndjson")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = fetch()
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+"\n")
    print(f"wrote {len(rows)} rows -> {out}")

if __name__ == "__main__": main()
