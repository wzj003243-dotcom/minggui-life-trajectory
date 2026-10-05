"""Conservatively canonicalize multi-source LifeGraph events.

Goals:
- one canonical event can carry multiple source/evidence families;
- exact/near-exact duplicates are collapsed without aggressive semantic guessing;
- source-specific event types are mapped to a stable cross-domain event_family;
- raw source rows remain recoverable through source/event ids.

This script intentionally does NOT merge events merely because they share a year/domain.
"""
from __future__ import annotations
import argparse,csv,gzip,json,hashlib,re
from collections import defaultdict
from pathlib import Path

def open_csv(path):
    return gzip.open(path,"rt",encoding="utf-8",newline="") if str(path).endswith(".gz") else open(path,"r",encoding="utf-8",newline="")

def source_family(s):
    s=(s or "").lower()
    if s.startswith("wikipedia"):return "wikipedia"
    if s=="wikidata":return "wikidata"
    if s=="openalex":return "openalex"
    if s=="musicbrainz":return "musicbrainz"
    return s or "unknown"

def event_family(event_type,domain):
    e=(event_type or "").lower()
    d=(domain or (e.split(".",1)[0] if "." in e else e) or "other").lower()
    rules=[
      ("education.complete",("graduat","education.complete","degree.complete")),
      ("education.start",("education.start","enroll","education.affiliation.start")),
      ("education.degree",("education.degree",)),
      ("education.affiliation",("education.affiliation",)),
      ("career.role_start",("career.position.start","career.employer.start","career.role_start","career.appointment")),
      ("career.role_end",("career.position.end","career.employer.end","career.retirement","career.role_end")),
      ("career.role",("career.position","career.employer","career.occupation","career.team","career.military_rank")),
      ("migration.move",("migration.residence","migration.cross_region","emigrat","immigrat","relocat")),
      ("creation.scholar_output",("creation.scholar_work",)),
      ("creation.music_output",("creation.music_release_group",)),
      ("creation.notable_work",("creation.notable_work",)),
      ("creation.publication",("creation.publication","creation.release")),
      ("creation.founding",("creation.founded","creation.organization_founded")),
      ("creation.discovery",("creation.discovery","creation.invention")),
      ("recognition.award",("recognition.award",)),
      ("recognition.election",("recognition.election",)),
      ("relationship.marriage",("relationship.marriage","relationship.spouse.start","relationship.spouse")),
      ("relationship.divorce",("relationship.divorce","relationship.spouse.end")),
      ("family.child_birth",("family.child_birth",)),
      ("organization.affiliation",("organization.member","organization.affiliation","organization.party")),
      ("performance.event",("performance.music_event",)),
      ("setback.legal",("setback.arrest","setback.imprisonment")),
      ("setback.financial",("setback.bankruptcy",)),
      ("setback.job_loss",("setback.job_loss",)),
    ]
    for fam,tokens in rules:
        if any(tok in e for tok in tokens):return fam
    return f"{d}.other"

def attrs(row):
    raw=row.get("attributes_json") or ""
    if not raw:return {}
    try:return json.loads(raw)
    except:return {}

def subject_key(row):
    a=attrs(row)
    for k in ("doi","openalex_work_id","musicbrainz_id","work_qid","subject_id"):
        v=(row.get(k) or a.get(k) or "").strip() if isinstance(row.get(k) or a.get(k) or "",str) else row.get(k) or a.get(k)
        if v:return str(v).lower()
    return (row.get("subject_id") or "").strip().lower()

def norm_date(row,key):
    return (row.get(key) or "").strip()

def exact_key(row):
    pid=(row.get("person_id") or "").strip()
    et=(row.get("event_type") or "").strip().lower()
    dom=(row.get("domain") or (et.split(".",1)[0] if "." in et else "")).strip().lower()
    d0=norm_date(row,"event_date_min")
    d1=norm_date(row,"event_date_max")
    subj=subject_key(row)
    # Subject-backed events can merge across source adapters if the same external object/date/type appears.
    # Subject-less events require exact type + exact interval; year-only narrative events stay distinct
    # from differently typed structured claims.
    return (pid,event_family(et,dom),et,d0,d1,subj)

def stable_id(key):
    return "lg:"+hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()[:20]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("output")
    ap.add_argument("inputs",nargs="+")
    args=ap.parse_args()
    groups=defaultdict(list)
    input_rows=0
    for raw in args.inputs:
        with open_csv(raw) as f:
            for r in csv.DictReader(f):
                if not (r.get("person_id") or "").strip():continue
                groups[exact_key(r)].append(r);input_rows+=1

    fields=[
      "canonical_event_id","person_id","domain","event_family","event_type",
      "event_date_min","event_date_max","temporal_precision","age_min","age_max","age_mid",
      "subject_id","source_families","source_count","evidence_row_count",
      "confidence_max","observable_from","member_event_ids","member_sources"
    ]
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    merged=0;cross_source=0;people=set()
    with gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for key,rows in groups.items():
            first=rows[0];et=(first.get("event_type") or "").strip()
            dom=(first.get("domain") or (et.split(".",1)[0] if "." in et else "") or "other").strip()
            sources=sorted({source_family(r.get("source_id")) for r in rows})
            conf=[]
            for r in rows:
                try:conf.append(float(r.get("confidence") or 0))
                except:pass
            member_ids=[(r.get("event_id") or "").strip() for r in rows if (r.get("event_id") or "").strip()]
            member_sources=[(r.get("source_id") or "").strip() for r in rows if (r.get("source_id") or "").strip()]
            wr.writerow({
              "canonical_event_id":stable_id(key),"person_id":first.get("person_id"),"domain":dom,
              "event_family":event_family(et,dom),"event_type":et,
              "event_date_min":first.get("event_date_min") or "","event_date_max":first.get("event_date_max") or "",
              "temporal_precision":first.get("temporal_precision") or "",
              "age_min":first.get("age_min") or "","age_max":first.get("age_max") or "","age_mid":first.get("age_mid") or "",
              "subject_id":first.get("subject_id") or subject_key(first),"source_families":"|".join(sources),
              "source_count":len(sources),"evidence_row_count":len(rows),"confidence_max":max(conf) if conf else "",
              "observable_from":max((r.get("observable_from") or "") for r in rows),
              "member_event_ids":"|".join(member_ids),"member_sources":"|".join(member_sources)
            })
            merged+=1;people.add(first.get("person_id"))
            if len(sources)>1:cross_source+=1
    report={
      "input_event_rows":input_rows,"canonical_event_rows":merged,
      "exact_duplicates_collapsed":input_rows-merged,"people":len(people),
      "canonical_events_with_multiple_source_families":cross_source,
      "policy":"exact conservative merge only; no same-year semantic guessing"
    }
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
