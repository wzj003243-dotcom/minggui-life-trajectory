"""Extract auditable date-bearing life-event candidates from Wikipedia biography plaintext.

This is intentionally high-recall and non-LLM. It does not decide that a sentence is true or
assign a final event label; it creates source-backed candidates for later adjudication.
"""
from __future__ import annotations
import argparse,csv,gzip,json,re
import mwparserfromhell
from pathlib import Path

YEAR=re.compile(r"\b(?:18|19|20)\d{2}\b")
AGE_EN=re.compile(r"\b(?:aged?|age)\s+(\d{1,2})\b",re.I)
AGE_ZH=re.compile(r"(\d{1,2})\s*岁")
SENTENCE=re.compile(r"(?<=[.!?。！？])\s+|\n+")

KEYWORDS={
 "education":[r"universit",r"college",r"school",r"graduat",r"enroll",r"studied",r"degree",r"学院",r"大学",r"毕业",r"入学",r"就读"],
 "career":[r"appointed",r"joined",r"worked",r"career",r"became",r"promot",r"retir",r"resign",r"任职",r"加入",r"工作",r"升任",r"辞职",r"退休"],
 "migration":[r"moved",r"emigrat",r"immigrat",r"relocat",r"returned to",r"exil",r"移居",r"迁往",r"搬到",r"回到",r"流亡"],
 "creation":[r"publish",r"released",r"wrote",r"directed",r"founded",r"launched",r"invent",r"discover",r"作品",r"出版",r"发表",r"创立",r"推出",r"发明",r"发现"],
 "recognition":[r"award",r"won",r"prize",r"honou?r",r"elected",r"nominat",r"获奖",r"获得",r"当选",r"提名"],
 "relationship":[r"married",r"divorc",r"separat",r"婚",r"离婚",r"分居"],
 "setback":[r"fired",r"dismissed",r"bankrupt",r"arrested",r"imprison",r"defeat",r"failed",r"破产",r"逮捕",r"监禁",r"失败",r"被解雇"]
}
COMPILED={k:[re.compile(x,re.I) for x in xs] for k,xs in KEYWORDS.items()}

def classify(s):
    scores={k:sum(bool(p.search(s)) for p in ps) for k,ps in COMPILED.items()}
    hits=[k for k,v in scores.items() if v]
    return hits,scores

def clean(s):return re.sub(r"\s+"," ",s).strip()

def wikitext_to_plain(raw):
    code=mwparserfromhell.parse(raw or "")
    # Narrative extraction should not treat infobox/template markup as prose.
    for node in list(code.filter_templates(recursive=True)):
        try:
            code.remove(node,recursive=True)
        except Exception:
            pass
    return code.strip_code(normalize=True,collapse=True) or ""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("biographies");ap.add_argument("output");args=ap.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    fields=["candidate_id","person_id","site","pageid","revision_id","revision_timestamp","source_url",
            "years","ages","candidate_domains","text","text_length","license"]
    rows=0;people=set();domain_counts={}
    with gzip.open(args.biographies,"rt",encoding="utf-8") as f,gzip.open(out,"wt",encoding="utf-8",newline="") as w:
        wr=csv.DictWriter(w,fieldnames=fields);wr.writeheader()
        for line in f:
            rec=json.loads(line);plain=wikitext_to_plain(rec.get("wikitext",""));parts=[clean(x) for x in SENTENCE.split(plain) if clean(x)]
            for i,s in enumerate(parts):
                years=YEAR.findall(s);ages=AGE_EN.findall(s)+AGE_ZH.findall(s)
                if not years and not ages:continue
                domains,scores=classify(s)
                if not domains:continue
                # Long paragraphs are clipped around the first explicit year/age marker.
                if len(s)>700:
                    markers=[m.start() for m in YEAR.finditer(s)]+[m.start() for m in AGE_EN.finditer(s)]+[m.start() for m in AGE_ZH.finditer(s)]
                    pivot=min(markers) if markers else 0;s=s[max(0,pivot-250):pivot+450]
                cid=f"{rec['person_id']}:{rec['site']}:{rec['revision_id']}:{i}"
                wr.writerow({
                  "candidate_id":cid,"person_id":rec["person_id"],"site":rec["site"],"pageid":rec["pageid"],
                  "revision_id":rec["revision_id"],"revision_timestamp":rec["revision_timestamp"],
                  "source_url":rec["source_url"],"years":"|".join(years),"ages":"|".join(ages),
                  "candidate_domains":"|".join(domains),"text":s,"text_length":len(s),"license":rec["license"]
                });rows+=1;people.add(rec["person_id"])
                for d in domains:domain_counts[d]=domain_counts.get(d,0)+1
    report={"candidate_rows":rows,"people_with_candidates":len(people),"candidate_domain_hits":domain_counts,
            "status":"high-recall candidates; not yet adjudicated life events"}
    out.with_name(out.name[:-7]+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
