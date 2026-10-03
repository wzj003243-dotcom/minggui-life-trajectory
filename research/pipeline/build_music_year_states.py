"""Convert MusicBrainz dated creative events into yearly creator-state vectors."""
from __future__ import annotations
import argparse,csv,gzip,json
from collections import Counter,defaultdict
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument("events");ap.add_argument("output");args=ap.parse_args()
    by=defaultdict(list)
    with gzip.open(args.events,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            try:y=int((r.get("event_date") or "")[:4])
            except:continue
            by[r["person_id"]].append((y,r))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=[
      "person_id","year","release_groups","performance_events","albums","singles","eps",
      "rolling_3y_release_groups","cumulative_release_groups","cumulative_performance_events",
      "years_since_first_release","release_gap_before_year","active_music_year"
    ]
    rows=people=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,items in by.items():
            years=sorted({y for y,_ in items});people+=1
            yearly=defaultdict(list)
            for y,r in items:yearly[y].append(r)
            release_hist={};cumrel=cumperf=0;first_release=None;last_release=None
            for y in range(min(years),max(years)+1):
                evs=yearly.get(y,[])
                rel=[e for e in evs if e.get("event_type")=="creation.music_release_group"]
                perf=[e for e in evs if e.get("event_type")=="performance.music_event"]
                sub=Counter((e.get("subtype") or "").lower() for e in rel)
                release_hist[y]=len(rel);cumrel+=len(rel);cumperf+=len(perf)
                gap=""
                if rel:
                    if first_release is None:first_release=y
                    if last_release is not None:gap=y-last_release
                    last_release=y
                rolling=sum(release_hist.get(k,0) for k in (y-2,y-1,y))
                wr.writerow({
                  "person_id":pid,"year":y,"release_groups":len(rel),"performance_events":len(perf),
                  "albums":sub["album"],"singles":sub["single"],"eps":sub["ep"],
                  "rolling_3y_release_groups":rolling,"cumulative_release_groups":cumrel,
                  "cumulative_performance_events":cumperf,
                  "years_since_first_release":"" if first_release is None else y-first_release,
                  "release_gap_before_year":gap,"active_music_year":int(bool(rel or perf))
                });rows+=1
    report={"people":people,"year_state_rows":rows,"features":"dated MusicBrainz core metadata only"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
