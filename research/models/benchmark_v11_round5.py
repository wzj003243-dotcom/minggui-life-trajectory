"""MingGui v1.1 Round 5: preregistered matched-history lift experiment.

This uses v1.1-recomputed labels under frozen v1.0 observation windows and the
identical person split, testing whether v1.1's richer *pre-cutoff history* adds
predictive value beyond history derivable from frozen v1.0.

This is not a BaZi experiment and does not compare raw v1.0 vs v1.1 label metrics.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from benchmark_final_v1_round4 import (
    CLASSES, EVENT_CLASSES, HGB_CFG, SEED, HORIZONS,
    bootstrap_pair, compose_horizon_predictions, expand_all_intervals,
    feature_columns, file_sha256, flatten_cutoffs,
    horizon_metrics, interval_metrics, make_hgb, model_probs, prior_probs,
)

SOURCE_SNAPSHOT_ID="7fce3b79-ebfc-40b2-a5f0-e91b28db6a02"
SOURCE_CANONICAL_SHA="2af1167d562c83789c0eaa0c0f7b793706ce2e17e9273c8c22450f80791dc5cf"
OLD_SNAPSHOT_ID="42628250-3a51-4b92-b4bd-12c7dec846a8"
PROTOCOL="v11-round5-matched-history-lift-v1"


def read_chunks(root: Path, prefix: str) -> list[dict]:
    paths=sorted(root.glob(f"{prefix}-*.json"))
    if not paths:
        raise ValueError(f"missing {prefix} chunks")
    rows=[]
    for path in paths:
        obj=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj,list):raise ValueError(f"unexpected JSON: {path}")
        rows.extend(obj)
    return rows


def flatten_arm(records: list[dict], arm: str) -> pd.DataFrame:
    rows=[]
    key="x_features_old" if arm=="old_history" else "x_features_new"
    for x in records:
        rows.append({
            "source_training_example_id":x["source_training_example_id"],
            "person_id":x["person_id"],
            "wikidata_id":x["wikidata_id"],
            "cutoff_age":x["cutoff_age"],
            "cutoff_date":x["cutoff_date"],
            "source_target_domain":x.get("target_domain"),
            "source_target_observable_from":x.get("target_observable_from"),
            "source_observation_end_date":x["observation_end_date"],
            "source_right_censored":x.get("target_canonical_event_key") is None,
            "split_name":x["split_name"],
            "fold":x.get("fold"),
            "placebo_eligible":False,
            "x_features":x[key],
        })
    return flatten_cutoffs(rows)


def checked_inputs(cutoffs: pd.DataFrame, periods: pd.DataFrame) -> dict:
    if len(cutoffs)!=13064:
        raise ValueError(f"cutoff count: {len(cutoffs)} != 13064")
    if len(periods)!=49909:
        raise ValueError(f"interval count: {len(periods)} != 49909")
    if int((periods.outcome_class!="no_event").sum())!=7283:
        raise ValueError("unexpected event count")
    if cutoffs.source_training_example_id.duplicated().any():
        raise ValueError("duplicate source cutoff")
    if periods.person_period_id.duplicated().any():
        raise ValueError("duplicate period id")
    if periods[["source_training_example_id","interval_index"]].duplicated().any():
        raise ValueError("duplicate cutoff/interval")
    if not set(periods.outcome_class).issubset(CLASSES):
        raise ValueError("unknown outcome class")
    if (periods.target_observable_from.notna() & (periods.target_observable_from<=periods.cutoff_date)).any():
        raise ValueError("target observable at/before cutoff")
    persons=cutoffs.groupby("person_id").split_name.nunique()
    if int((persons>1).sum()):
        raise ValueError("person leaked into multiple splits")
    percutoff=periods.groupby("source_training_example_id")
    if (percutoff.apply(lambda g: int((g.outcome_class!="no_event").sum()),include_groups=False)>1).any():
        raise ValueError("multiple first events per cutoff")
    return {
        "cutoffs":len(cutoffs),
        "periods":len(periods),
        "people":int(cutoffs.person_id.nunique()),
        "splits":cutoffs.groupby("split_name").person_id.nunique().to_dict(),
        "outcomes":periods.outcome_class.value_counts().to_dict(),
        "checks":"passed",
    }


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("output_dir")
    args=parser.parse_args()
    inp=Path(args.input_dir)
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    (out/"models").mkdir(exist_ok=True)

    records=read_chunks(inp,"cutoffs")
    prows=read_chunks(inp,"periods")
    periods=pd.DataFrame(prows)
    periods["person_period_id"]=periods.person_period_id.astype(int)
    for key in ["source_training_example_id","person_id","cutoff_age","interval_index",
                "interval_start_year","interval_end_year","interval_width_years"]:
        periods[key]=periods[key].astype(int)
    periods["cutoff_date"]=pd.NaT
    periods["target_observable_from"]=pd.to_datetime(periods["target_observable_from"],errors="coerce")

    arms={}
    for key in ["old_history","v11_history"]:
        cut=flatten_arm(records,key)
        if key=="old_history":
            # Add cutoff dates for preflight checks only; periods will merge once.
            periods["cutoff_date"]=periods.source_training_example_id.map(
                cut.set_index("source_training_example_id").cutoff_date
            )
            periods["cutoff_date"]=pd.to_datetime(periods.cutoff_date)
        arms[key]=cut
    audit=checked_inputs(arms["old_history"],periods)
    for key,frame in arms.items():
        if not np.array_equal(frame.source_training_example_id.to_numpy(),
                              arms["old_history"].source_training_example_id.to_numpy()):
            raise ValueError("arms not identically aligned")

    preds=[]
    metrics=[]
    horizons=[]
    manifest={}
    old_cut=arms["old_history"]
    data_old=periods.merge(old_cut,on=["source_training_example_id","person_id","cutoff_age"],
                           how="left",validate="many_to_one",suffixes=("","_cut"))
    data_old["split_name"]=data_old.split_name.astype(str)
    assert data_old.split_name.notna().all()

    tr=data_old[data_old.split_name=="train"]
    for split in ["validation","test"]:
        part=data_old[data_old.split_name==split].copy()
        p=prior_probs(tr,part)
        y=part.outcome_class
        m=interval_metrics(y,p)
        metrics.append({"arm":"interval_prior","split":split,**{k:v for k,v in m.items() if k!="per_class"},"per_class":m["per_class"]})
        prior_rows=part[["person_period_id","person_id","source_training_example_id","interval_index","outcome_class"]].copy()
        prior_rows["arm"]="interval_prior";prior_rows["split_name"]=split
        prior_rows["y_true"]=prior_rows.outcome_class
        for i,c in enumerate(CLASSES):prior_rows[f"p_{c}"]=p[:,i]
        preds.append(prior_rows)
        grid=expand_all_intervals(old_cut[old_cut.split_name==split].copy())
        probs=prior_probs(tr,grid)
        horizons.append(compose_horizon_predictions(
            old_cut[old_cut.split_name==split].copy(),grid,probs,
            "interval_prior","interval_prior"
        ).assign(arm="interval_prior"))

    for arm in ["old_history","v11_history"]:
        cut=arms[arm]
        work=periods.drop(columns=["cutoff_date"]).merge(
            cut,on=["source_training_example_id","person_id","cutoff_age"],
            how="left",validate="many_to_one"
        )
        if work.split_name.isna().any():raise ValueError(f"{arm} missing cutoff assignment")
        num,cat=feature_columns(work,"history_reality_v1")
        cols=num+cat
        model=make_hgb(num,cat)
        train=work[work.split_name=="train"].copy()
        model.fit(train[cols],train.outcome_class)
        model_path=out/"models"/f"hgb__{arm}.joblib"
        joblib.dump(model,model_path)
        manifest[arm]={
            "model_family":"hist_gradient_boosting",
            "capacity":"frozen-round4-hgb-small",
            "hgb_config":HGB_CFG,
            "train_rows":len(train),
            "train_people":int(train.person_id.nunique()),
            "numeric_features":num,
            "categorical_features":cat,
            "model_file":str(model_path.relative_to(out)),
        }
        for split in ["validation","test"]:
            part=work[work.split_name==split].copy()
            p=model_probs(model,part,cols)
            m=interval_metrics(part.outcome_class,p)
            metrics.append({"arm":arm,"split":split,**{k:v for k,v in m.items() if k!="per_class"},"per_class":m["per_class"]})
            pr=part[["person_period_id","person_id","source_training_example_id","interval_index","outcome_class"]].copy()
            pr["arm"]=arm;pr["split_name"]=split;pr["y_true"]=pr.outcome_class
            for i,c in enumerate(CLASSES):pr[f"p_{c}"]=p[:,i]
            preds.append(pr)
            grid=expand_all_intervals(cut[cut.split_name==split].copy())
            gp=model_probs(model,grid,cols)
            horizons.append(compose_horizon_predictions(
                cut[cut.split_name==split].copy(),grid,gp,"hist_gradient_boosting",arm
            ).assign(arm=arm))

    preds_df=pd.concat(preds,ignore_index=True)
    metric_df=pd.DataFrame(metrics)
    horizon_df=pd.concat(horizons,ignore_index=True)
    hmet=pd.DataFrame(horizon_metrics(horizon_df))
    test=preds_df[preds_df.split_name=="test"]
    a=test[test.arm=="v11_history"].copy()
    b=test[test.arm=="old_history"].copy()
    paired=bootstrap_pair(a,b,reps=1000)

    # Predeclared sparse-history diagnostic: group by old-history event count.
    old_count=arms["old_history"].set_index("source_training_example_id").history_canonical_event_count
    sparse={}
    for name,predicate in [
        ("zero_history",lambda s:s==0),
        ("one_history",lambda s:s==1),
        ("two_to_four_history",lambda s:(s>=2)&(s<=4)),
        ("five_plus_history",lambda s:s>=5),
    ]:
        aa=a[a.source_training_example_id.map(old_count).pipe(predicate)]
        bb=b[b.source_training_example_id.map(old_count).pipe(predicate)]
        sparse[name]=bootstrap_pair(aa,bb,reps=1000) if len(aa)>0 else {"paired_rows":0}

    safe_metrics=metric_df.copy()
    safe_metrics["per_class"]=safe_metrics.per_class.map(json.dumps)
    safe_metrics.to_csv(out/"interval_metrics.csv",index=False)
    preds_df.to_csv(out/"interval_predictions.csv.gz",index=False,compression="gzip")
    horizon_df.to_csv(out/"horizon_predictions.csv.gz",index=False,compression="gzip")
    hmet.assign(details=hmet.details.map(json.dumps)).to_csv(out/"horizon_metrics.csv",index=False)
    (out/"model_manifest.json").write_text(json.dumps(manifest,indent=2,default=str))
    summary={
        "round":"v1.1-round5",
        "protocol":PROTOCOL,
        "source_snapshot_id":SOURCE_SNAPSHOT_ID,
        "source_canonical_sha256":SOURCE_CANONICAL_SHA,
        "old_snapshot_id":OLD_SNAPSHOT_ID,
        "seed":SEED,
        "models":["interval_prior","hgb_old_history","hgb_v11_history"],
        "hgb_capacity":HGB_CFG,
        "data_audit":audit,
        "test_metrics":metric_df[metric_df.split=="test"][
            ["arm","n","log_loss","brier_multiclass","ece_10bin","event_vs_no_event_brier",
             "macro_f1","conditional_domain_log_loss","conditional_domain_macro_f1"]
        ].to_dict(orient="records"),
        "validation_metrics":metric_df[metric_df.split=="validation"][
            ["arm","n","log_loss","brier_multiclass","ece_10bin","event_vs_no_event_brier",
             "macro_f1"]
        ].to_dict(orient="records"),
        "person_cluster_bootstrap_v11_minus_v10_history":paired,
        "sparse_history_bootstrap":sparse,
        "input_json_sha256":{
            p.name:file_sha256(p) for p in sorted(inp.glob("*.json"))
        },
        "environment":{
            "python":sys.version,"platform":platform.platform(),
            "sklearn":sklearn.__version__,"numpy":np.__version__,"pandas":pd.__version__,
        },
        "limitations":[
            "The outcome is the next documented canonical event, not the next real-world event.",
            "Historic observation windows were fixed from v1.0; newly discovered records may leave some events outside the old observation window.",
            "Wikipedia revision text is retrospective; this is not a historically timestamped information-availability replay.",
            "No hyperparameter selection or test-driven tuning.",
            "BaZi is not part of the two history-comparison arms.",
        ],
    }
    (out/"round5_summary.json").write_text(json.dumps(summary,indent=2,default=str))
    sums={str(p.relative_to(out)):file_sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    (out/"SHA256SUMS.json").write_text(json.dumps(sums,indent=2))
    print(json.dumps({
        "protocol":PROTOCOL,"data_audit":audit,
        "test_metrics":summary["test_metrics"],
        "paired":paired
    },indent=2,default=str))

if __name__=="__main__":
    main()
