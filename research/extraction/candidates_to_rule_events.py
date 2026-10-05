"""Convert only high-precision biography candidates into conservative LifeGraph events.

Acceptance rule:
- exactly one explicit year
- exactly one candidate domain
- a domain-specific trigger phrase that maps to a concrete event type

Everything else stays in the candidate/review layer. This is intentionally precision-first.
"""
from __future__ import annotations
import argparse,csv,gzip,json,re
from datetime import date
from pathlib import Path

RULES=[
 ("education.complete",[r"graduat",r"毕业"]),
 ("education.start",[r"enroll",r"entered .*univers",r"began .*univers",r"入学",r"就读"]),
 ("career.retirement",[r"retir",r"退休"]),
 ("career.appointment",[r"appoint",r"became .*professor",r"became .*director",r"任命",r"升任"]),
 ("career.role_start",[r"joined",r"began work",r"started work",r"任职",r"加入"]),
 ("migration.cross_region",[r"emigrat",r"immigrat",r"moved to",r"relocat",r"移居",r"迁往",r"搬到"]),
 ("creation.publication",[r"publish",r"出版",r"发表"]),
 ("creation.release",[r"released",r"发行",r"推出"]),
 ("organization.found",[r"founded",r"co-founded",r"established (?:a|the) (?:company|foundation|organization|party|institute)",r"创立",r"创办",r"成立.*(?:公司|基金会|组织|政党|研究所)"]),
 ("creation.invention",[r"invent",r"发明"]),
 ("creation.discovery",[r"discover",r"发现"]),
 ("recognition.award",[r"won .*award",r"received .*award",r"awarded",r"prize",r"获奖",r"获得.*奖"]),
 ("recognition.election",[r"elected",r"当选"]),
 ("relationship.marriage",[r"married",r"结婚",r"成婚"]),
 ("relationship.divorce",[r"divorc",r"离婚"]),
 ("family.child_birth",[r"(?:son|daughter|child) was born",r"gave birth to",r"had (?:a|their) (?:son|daughter|child)",r"儿子.*出生",r"女儿.*出生",r"兒子.*出生",r"女兒.*出生"]),
 ("family.parent_loss",[r"(?:mother|father) died",r"(?:母亲|父亲|母親|父親).*去世"]),
 ("legal.arrest",[r"arrest",r"逮捕"]),
 ("legal.imprisonment",[r"imprison",r"监禁",r"監禁"]),
 ("legal.conviction",[r"convicted",r"定罪"]),
 ("legal.acquittal",[r"acquitted",r"无罪",r"無罪"]),
 ("setback.bankruptcy",[r"bankrupt",r"破产"]),
 ("setback.job_loss",[r"fired",r"dismissed",r"被解雇"])
]
COMPILED=[(name,[re.compile(x,re.I) for x in xs]) for name,xs in RULES]

def births(path):
    out={}
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            q=(r.get("wikidata_id") or "").strip();d=(r.get("birth_date") or "")[:10]
            try:
                if q and d:out[q]=date.fromisoformat(d)
            except:pass
    return out

def age(b,y):
    mid=date(y,7,2)
    return round((mid-b).days/365.2425,4)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("candidates");ap.add_argument("canonical_births");ap.add_argument("output")
    args=ap.parse_args();bmap=births(Path(args.canonical_births))
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["event_id","person_id","domain","event_type","event_date_min","event_date_max","temporal_precision",
            "age_mid","source_id","source_url","revision_id","candidate_id","evidence_text",
            "extraction_method","confidence","observable_from"]
    rows=0;people=set();unmatched=0
    with gzip.open(args.candidates,"rt",encoding="utf-8",newline="") as f,gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        r=csv.DictReader(f);wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for x in r:
            years=[y for y in (x.get("years") or "").split("|") if y]
            domains=[d for d in (x.get("candidate_domains") or "").split("|") if d]
            if len(set(years))!=1 or len(set(domains))!=1:continue
            text=x.get("text") or "";mapped=None
            for name,ps in COMPILED:
                if name.split(".",1)[0]!=domains[0]:continue
                if any(p.search(text) for p in ps):mapped=name;break
            if not mapped:unmatched+=1;continue
            y=int(years[0]);b=bmap.get(x["person_id"])
            wr.writerow({
              "event_id":f"bio:{x['candidate_id']}","person_id":x["person_id"],"domain":domains[0],
              "event_type":mapped,"event_date_min":f"{y:04d}-01-01","event_date_max":f"{y:04d}-12-31",
              "temporal_precision":"year","age_mid":"" if not b else age(b,y),
              "source_id":f"wikipedia:{x.get('site','')}","source_url":x.get("source_url") or "",
              "revision_id":x.get("revision_id") or "","candidate_id":x["candidate_id"],
              "evidence_text":text,"extraction_method":"rule-from-revision-text",
              "confidence":0.82,"observable_from":f"{y:04d}-12-31"
            });rows+=1;people.add(x["person_id"])
    report={"accepted_rule_events":rows,"people":len(people),"single_domain_year_candidates_without_rule_match":unmatched,
            "policy":"precision-first; ambiguous/multi-year candidates remain for adjudication"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
