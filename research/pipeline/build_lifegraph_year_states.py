"""Build cutoff-safe annual LifeGraph state vectors from normalized life events.

High-frequency outputs (papers/releases/performances) are collapsed to one effective trajectory
point per person-year-family for generic trajectory features. Specialized academic/music tables
retain detailed production intensity separately.

Only events observable by the end of a state year contribute to that year's state.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path

DOMAINS=("education","career","migration","creation","recognition","organization","relationship","family","setback","finance","legal","performance")
HIGH_FREQUENCY={"creation.scholar_output","creation.music_output","performance.event"}

def entropy(c):
    n=sum(c.values())
    return 0.0 if not n else -sum((v/n)*math.log(v/n) for v in c.values() if v)

def source_families(row):
    raw=(row.get("source_families") or "").strip()
    if raw:return [x for x in raw.split("|") if x]
    s=(row.get("source_id") or "").lower()
    if s.startswith("wikipedia"):return ["wikipedia"]
    if s=="wikidata":return ["wikidata"]
    if s=="openalex":return ["openalex"]
    if s=="musicbrainz":return ["musicbrainz"]
    return [s or "unknown"]

def family(row):
    fam=(row.get("event_family") or "").strip()
    if fam:return fam
    e=(row.get("event_type") or "").lower()
    if "creation.scholar_work" in e:return "creation.scholar_output"
    if "creation.music_release_group" in e:return "creation.music_output"
    if "performance.music_event" in e:return "performance.event"
    if "career.position.start" in e or "career.employer.start" in e or "career.role_start" in e or "career.appointment" in e:return "career.role_start"
    if "career.position.end" in e or "career.employer.end" in e or "career.retirement" in e:return "career.role_end"
    if "education.affiliation.start" in e or "education.start" in e:return "education.start"
    if "education.affiliation.end" in e or "education.complete" in e:return "education.end"
    if "relationship.spouse.start" in e or "relationship.marriage" in e:return "relationship.start"
    if "relationship.spouse.end" in e or "relationship.divorce" in e:return "relationship.end"
    if "migration" in e:return "migration.move"
    if "recognition" in e:return "recognition.event"
    return e or ((row.get("domain") or "other")+".other")

def domain(row):
    return (row.get("domain") or (row.get("event_type") or "").split(".",1)[0] or "other").strip()

def subject(row):
    return (row.get("subject_id") or "").strip()

def event_year(row):
    raw=(row.get("observable_from") or row.get("event_date_max") or row.get("event_date_min") or "").strip()
    try:return int(raw[:4])
    except:return None

def open_events(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        yield from csv.DictReader(f)

def effective_year_points(evs,year):
    points=[];seen_hf=set()
    for r in evs:
        fam=family(r)
        if fam in HIGH_FREQUENCY:
            key=(year,fam)
            if key in seen_hf:continue
            seen_hf.add(key)
        points.append(r)
    return points

def rolling(counter_by_year,year,width,key=None):
    total=0
    for yy in range(year-width+1,year+1):
        c=counter_by_year.get(yy,Counter())
        total+=sum(c.values()) if key is None else c.get(key,0)
    return total

def previous_window(counter_by_year,year,width,key):
    return sum(counter_by_year.get(yy,Counter()).get(key,0) for yy in range(year-2*width+1,year-width+1))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("output")
    ap.add_argument("--additional-events",nargs="*",default=[])
    args=ap.parse_args()

    by=defaultdict(list)
    for raw in [args.events]+list(args.additional_events):
        for r in open_events(raw):
            y=event_year(r);pid=(r.get("person_id") or "").strip()
            if y is not None and pid:by[pid].append((y,r))

    base_fields=[
      "person_id","year",
      "events_this_year","effective_points_this_year","cumulative_events","cumulative_effective_points",
      "domains_this_year","effective_domains_this_year","cumulative_domain_breadth","cumulative_domain_entropy",
      "source_families_this_year","cumulative_source_family_breadth",
      "rolling_3y_events","rolling_3y_effective_points","rolling_5y_effective_points",
      "rolling_5y_domain_breadth","event_family_entropy_5y",
      "creation_momentum_3y","recognition_rolling_5y","migration_rolling_5y",
      "career_transitions_cumulative","migration_transitions_cumulative","relationship_transitions_cumulative",
      "active_career_roles","active_education_affiliations","active_relationships",
      "years_since_last_event","years_since_last_career","years_since_last_migration",
      "years_since_last_creation","years_since_last_recognition",
      "event_type_switches_cumulative"
    ]
    fields=base_fields+[f"year_count__{d}" for d in DOMAINS]+[f"effective_year_count__{d}" for d in DOMAINS]+[f"cum_effective__{d}" for d in DOMAINS]

    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    rows=people_count=0
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for pid,items in by.items():
            people_count+=1
            yearly=defaultdict(list)
            for y,r in items:yearly[y].append(r)
            years=sorted(yearly)
            raw_hist={};eff_hist={};family_hist={}
            cum_eff=Counter();cum_events=0;cum_eff_n=0;cum_sources=Counter()
            last_event_year=None;last_family=None;switches=0
            last_domain_year={d:None for d in DOMAINS}
            career_trans=migration_trans=relationship_trans=0
            active_career=set();active_edu=set();active_rel=set()

            for y in range(min(years),max(years)+1):
                evs=sorted(yearly.get(y,[]),key=lambda r:(r.get("event_date_min",""),r.get("event_id",""),r.get("canonical_event_id","")))
                eff=effective_year_points(evs,y)
                rawc=Counter(domain(r) for r in evs)
                effc=Counter(domain(r) for r in eff)
                famc=Counter(family(r) for r in eff)
                raw_hist[y]=rawc;eff_hist[y]=effc;family_hist[y]=famc

                source_now=Counter()
                for r in evs:
                    for src in source_families(r):source_now[src]+=1
                    fam=family(r);subj=subject(r)
                    if fam=="career.role_start":
                        career_trans+=1
                        if subj:active_career.add(subj)
                    elif fam=="career.role_end":
                        career_trans+=1
                        if subj:active_career.discard(subj)
                    elif fam=="education.start":
                        if subj:active_edu.add(subj)
                    elif fam=="education.end":
                        if subj:active_edu.discard(subj)
                    elif fam=="relationship.start":
                        relationship_trans+=1
                        if subj:active_rel.add(subj)
                    elif fam=="relationship.end":
                        relationship_trans+=1
                        if subj:active_rel.discard(subj)
                    elif fam=="migration.move":
                        migration_trans+=1
                    last_event_year=y

                for r in eff:
                    fam=family(r)
                    if last_family is not None and fam and fam!=last_family:switches+=1
                    if fam:last_family=fam
                for d,v in effc.items():
                    if v and d in last_domain_year:last_domain_year[d]=y

                cum_events+=len(evs);cum_eff_n+=len(eff);cum_eff.update(effc);cum_sources.update(source_now)

                fam5=Counter();dom5=set()
                for yy in range(y-4,y+1):
                    fam5.update(family_hist.get(yy,Counter()))
                    dom5.update(k for k,v in eff_hist.get(yy,Counter()).items() if v)

                creation3=rolling(eff_hist,y,3,"creation")
                creation_prev3=previous_window(eff_hist,y,3,"creation")
                row={
                  "person_id":pid,"year":y,
                  "events_this_year":len(evs),"effective_points_this_year":len(eff),
                  "cumulative_events":cum_events,"cumulative_effective_points":cum_eff_n,
                  "domains_this_year":len([k for k,v in rawc.items() if v]),
                  "effective_domains_this_year":len([k for k,v in effc.items() if v]),
                  "cumulative_domain_breadth":len([k for k,v in cum_eff.items() if v]),
                  "cumulative_domain_entropy":round(entropy(cum_eff),6),
                  "source_families_this_year":len(source_now),
                  "cumulative_source_family_breadth":len(cum_sources),
                  "rolling_3y_events":sum(sum(raw_hist.get(yy,Counter()).values()) for yy in range(y-2,y+1)),
                  "rolling_3y_effective_points":sum(sum(eff_hist.get(yy,Counter()).values()) for yy in range(y-2,y+1)),
                  "rolling_5y_effective_points":sum(sum(eff_hist.get(yy,Counter()).values()) for yy in range(y-4,y+1)),
                  "rolling_5y_domain_breadth":len(dom5),
                  "event_family_entropy_5y":round(entropy(fam5),6),
                  "creation_momentum_3y":creation3-creation_prev3,
                  "recognition_rolling_5y":rolling(eff_hist,y,5,"recognition"),
                  "migration_rolling_5y":rolling(eff_hist,y,5,"migration"),
                  "career_transitions_cumulative":career_trans,
                  "migration_transitions_cumulative":migration_trans,
                  "relationship_transitions_cumulative":relationship_trans,
                  "active_career_roles":len(active_career),
                  "active_education_affiliations":len(active_edu),
                  "active_relationships":len(active_rel),
                  "years_since_last_event":"" if last_event_year is None else y-last_event_year,
                  "years_since_last_career":"" if last_domain_year["career"] is None else y-last_domain_year["career"],
                  "years_since_last_migration":"" if last_domain_year["migration"] is None else y-last_domain_year["migration"],
                  "years_since_last_creation":"" if last_domain_year["creation"] is None else y-last_domain_year["creation"],
                  "years_since_last_recognition":"" if last_domain_year["recognition"] is None else y-last_domain_year["recognition"],
                  "event_type_switches_cumulative":switches
                }
                for d in DOMAINS:
                    row[f"year_count__{d}"]=rawc[d]
                    row[f"effective_year_count__{d}"]=effc[d]
                    row[f"cum_effective__{d}"]=cum_eff[d]
                wr.writerow(row);rows+=1

    report={
      "people":people_count,"year_state_rows":rows,"domains":list(DOMAINS),
      "input_event_files":1+len(args.additional_events),
      "high_frequency_collapse":"papers/music releases/performances -> max one effective point per person-year-family for generic trajectory features",
      "cutoff_rule":"all features use events observable by end of state year",
      "state_features":[
        "effective activity","domain breadth/entropy","3y/5y momentum","family volatility",
        "time-since-domain-event","career/migration/relationship transitions","active role proxies"
      ]
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
