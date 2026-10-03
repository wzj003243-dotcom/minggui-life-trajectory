"""Benchmark v0.1 — does compact BaZi signal predict the next observed life-event domain?

Task
----
For a birth-verified timed cohort, create person-cutoff rows at ages 18/25/30/40.
Use only events fully observable before the cutoff as history, then predict the domain of
that person's next *observed structured* Wikidata life event.

Target classes:
  career | recognition | relationship | other

Comparisons:
  1. reality baseline
  2. raw birth/calendar baseline
  3. compact objective BaZi features
  4. reality + compact BaZi
  5. decade-stratified shuffled-BaZi placebo

Important: this benchmark measures predictability of *documented public-biography event
sequences*, not metaphysical truth and not general-population life probabilities.
"""
from __future__ import annotations
import argparse, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, log_loss
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings("ignore")

CUTS=(18,25,30,40)
TARGET_MAIN={"career","recognition","relationship"}

def target_domain(x: str) -> str:
    return x if x in TARGET_MAIN else "other"

def model(seed: int):
    return Pipeline([
        ("impute",SimpleImputer(strategy="median")),
        ("scale",StandardScaler()),
        ("clf",SGDClassifier(
            loss="log_loss",alpha=.002,max_iter=1200,tol=1e-3,
            class_weight="balanced",random_state=seed,n_jobs=1
        ))
    ])

def score(m,test,cols):
    pred=m.predict(test[cols]);proba=m.predict_proba(test[cols])
    return {
      "macro_f1":f1_score(test.target,pred,average="macro",zero_division=0),
      "accuracy":accuracy_score(test.target,pred),
      "balanced_accuracy":balanced_accuracy_score(test.target,pred),
      "log_loss":log_loss(test.target,proba,labels=m.classes_)
    }

def build_rows(people,events):
    people=people.drop_duplicates("wikidata_id").set_index("wikidata_id")
    events=events[events.person_id.isin(people.index)].copy()
    for c in ["age_min","age_max","age_mid"]:
        events[c]=pd.to_numeric(events[c],errors="coerce")
    events=events[events.age_mid.notna()]
    domains=sorted(events.domain.dropna().unique())
    rows=[]
    for pid,p in people.iterrows():
        pe=events[events.person_id==pid].sort_values(["age_mid","age_min","event_date_min"])
        if pe.empty:continue
        for cutoff in CUTS:
            past=pe[pe.age_max<=cutoff];future=pe[pe.age_min>cutoff]
            if future.empty:continue
            nxt=future.iloc[0]
            bd=pd.to_datetime(p.get("birth_date_normalized"),errors="coerce")
            r={
              "person_id":pid,"cutoff_age":cutoff,"target":target_domain(nxt.domain),
              "gender_num":{"M":1,"F":0}.get(p.get("gender"),.5),
              "birth_year":bd.year if pd.notna(bd) else np.nan,
              "birth_month":bd.month if pd.notna(bd) else np.nan,
              "birth_day":bd.day if pd.notna(bd) else np.nan,
              "past_event_total":len(past)
            }
            bt=str(p.get("birth_time_local") or "")
            try:r["birth_hour"],r["birth_minute"]=map(int,bt.split(":")[:2])
            except:r["birth_hour"]=r["birth_minute"]=np.nan
            for d in domains:r[f"past_domain__{d}"]=int((past.domain==d).sum())
            for c in people.columns:
                if c.startswith("bazi__"):r[c]=p[c]
            rows.append(r)
    return pd.DataFrame(rows)

def compact_bazi_cols(df):
    tokens=[
      "element_entropy","element_imbalance","visible_element_","hidden_element_","hidden_gan_",
      "visible_tengod_","hidden_tengod_","zhi_","gan_he","gan_chong","sanhe_complete","sanhui_complete"
    ]
    return [c for c in df if c.startswith("bazi__") and pd.api.types.is_numeric_dtype(df[c])
            and df[c].nunique(dropna=True)>1 and any(t in c for t in tokens)]

def shuffled_bazi(part,person_bazi,bcols,seed):
    rng=np.random.default_rng(seed);ids=part.person_id.unique()
    p=person_bazi.loc[ids].copy();p["decade"]=(p.birth_year//10*10).fillna(-1)
    donor={}
    for _,g in p.groupby("decade"):
        src=g.index.to_numpy();dst=src.copy();rng.shuffle(dst);donor.update(dict(zip(src,dst)))
    mapped=pd.DataFrame(person_bazi.loc[[donor[x] for x in ids],bcols].to_numpy(),index=ids,columns=bcols)
    return part.drop(columns=bcols).join(mapped,on="person_id")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("people");ap.add_argument("events");ap.add_argument("outdir")
    args=ap.parse_args()
    out=Path(args.outdir);out.mkdir(parents=True,exist_ok=True)
    ppl=pd.read_csv(args.people);ev=pd.read_csv(args.events)
    df=build_rows(ppl,ev);df.to_csv(out/"benchmark_rows.csv.gz",index=False,compression="gzip")
    past=[c for c in df if c.startswith("past_domain__")]
    reality=["birth_year","gender_num","cutoff_age","past_event_total"]+past
    raw=["birth_year","birth_month","birth_day","birth_hour","birth_minute","cutoff_age"]
    bazi=compact_bazi_cols(df)
    person_bazi=df[["person_id","birth_year"]+bazi].drop_duplicates("person_id").set_index("person_id")

    rows=[]
    seeds=[11,17,23,29,37,43,51,59,67,73,79,83,89,97,103,109,113,127,131,139]
    for rep,seed in enumerate(seeds):
        a,b=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=seed).split(df,df.target,groups=df.person_id))
        tr=df.iloc[a].copy();te=df.iloc[b].copy()
        for name,cols in [
          ("reality",reality),("raw_birth",raw),
          ("bazi_compact",bazi+["cutoff_age"]),("reality_plus_bazi",reality+bazi)
        ]:
            m=model(seed);m.fit(tr[cols],tr.target)
            rows.append({"repeat":rep,"seed":seed,"model":name,**score(m,te,cols)})
    results=pd.DataFrame(rows);results.to_csv(out/"results_20_splits.csv",index=False)
    summary=results.groupby("model").agg(
      macro_f1_mean=("macro_f1","mean"),macro_f1_std=("macro_f1","std"),
      accuracy_mean=("accuracy","mean"),balanced_accuracy_mean=("balanced_accuracy","mean"),
      log_loss_mean=("log_loss","mean")
    ).reset_index()
    real=results[results.model=="reality_plus_bazi"].set_index("repeat")
    base=results[results.model=="reality"].set_index("repeat")
    delta=real.macro_f1-base.macro_f1
    report={
      "people_in_rows":int(df.person_id.nunique()),"person_cutoff_rows":len(df),
      "target_counts":df.target.value_counts().to_dict(),"compact_bazi_numeric_features":len(bazi),
      "summary":summary.to_dict(orient="records"),
      "reality_plus_bazi_minus_reality_macro_f1_mean":float(delta.mean()),
      "positive_splits":int((delta>0).sum()),"total_splits":len(delta),
      "limitations":[
        "Wikidata structured events are incomplete and unevenly documented.",
        "This is a public-figure cohort, not an ordinary population cohort.",
        "Target is next observed documented event domain, not the person's true next life event.",
        "Group-random person split is provisional; forward-era/geography holdouts are required next."
      ]
    }
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
