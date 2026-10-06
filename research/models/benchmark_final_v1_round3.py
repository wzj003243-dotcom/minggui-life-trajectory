"""MingGui final v1 — Round 3 distribution-shift holdouts.

Uses the exact hgb_small configuration frozen by Round 2.
No hyperparameter selection is performed in Round 3.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import f1_score
from sklearn.utils.class_weight import compute_sample_weight

import benchmark_final_v1_round2 as r2

PROTOCOL_KEY = "next-canonical-domain-generalization-round3-v1"
ALLOWED_SCENARIOS = {
    "forward_era_v1",
    "geo_us_holdout_v1",
    "geo_france_holdout_v1",
}
FROZEN_CFG = {
    "key": "hgb_small",
    "learning_rate": 0.05,
    "max_iter": 250,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 30,
    "l2_regularization": 2.0,
}
VARIANTS = r2.VARIANTS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--scenario", required=True)
    args = ap.parse_args()
    scenario = args.scenario
    if scenario not in ALLOWED_SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")

    inp = Path(args.input_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "models").mkdir(exist_ok=True)

    records = []
    for p in sorted(inp.glob("chunk-*.json")):
        rows = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{p} is not a row array")
        records.extend(rows)
    if len(records) != 7465:
        raise ValueError(f"expected 7465 frozen classification rows, got {len(records)}")

    df = r2.flatten_rows(records).sort_values("training_example_id").reset_index(drop=True)
    split_counts = df.groupby("split_name").size().to_dict()
    if set(split_counts) != {"train", "validation", "test"}:
        raise ValueError(split_counts)

    metric_rows = []
    pred_rows = []
    raw_metric_rows = []
    model_manifest = {}

    for variant in VARIANTS:
        model, num, cat, work = r2.fit_model(df, variant, FROZEN_CFG)
        cols = num + cat
        train = work[work.split_name == "train"].copy()
        val = work[work.split_name == "validation"].copy()
        test = work[work.split_name == "test"].copy()

        model_path = out / "models" / f"{variant}.joblib"
        joblib.dump(model, model_path)
        transformed_dim = int(model.named_steps["pre"].transform(train[cols].head(1)).shape[1])
        model_manifest[variant] = {
            "scenario": scenario,
            "frozen_config": FROZEN_CFG,
            "train_rows": int(len(train)),
            "validation_rows": int(len(val)),
            "test_rows": int(len(test)),
            "train_people": int(train.person_id.nunique()),
            "validation_people": int(val.person_id.nunique()),
            "test_people": int(test.person_id.nunique()),
            "numeric_features": num,
            "categorical_features": cat,
            "transformed_feature_dim": transformed_dim,
            "model_file": str(model_path.relative_to(out)),
        }

        for part_name, part in [("validation", val), ("test", test)]:
            met, pred, prob = r2.eval_part(model, part, cols)
            metric_rows.append({
                "model_family": "hist_gradient_boosting",
                "feature_variant": variant,
                "split_name": part_name,
                **{k: v for k, v in met.items() if k != "per_class"},
                "details": met["per_class"],
            })
            for i, (_, row) in enumerate(part.iterrows()):
                pred_rows.append({
                    "model_family": "hist_gradient_boosting",
                    "feature_variant": variant,
                    "training_example_id": int(row.training_example_id),
                    "person_id": int(row.person_id),
                    "split_name": part_name,
                    "y_true": row.y_class_4,
                    "y_pred": pred[i],
                    **{f"p_{c}": float(prob[i, j]) for j, c in enumerate(r2.CLASSES)},
                })

        # Finer raw-domain diagnostic with exactly the same frozen capacity.
        raw_classes = sorted(train.y_raw_domain.unique())
        raw_model = r2.make_model(num, cat, FROZEN_CFG)
        raw_weights = compute_sample_weight(class_weight="balanced", y=train.y_raw_domain)
        raw_model.fit(train[cols], train.y_raw_domain, clf__sample_weight=raw_weights)
        for part_name, part in [("validation", val), ("test", test)]:
            raw_pred = raw_model.predict(part[cols])
            labels = sorted(set(raw_classes) | set(part.y_raw_domain.unique()))
            score = f1_score(
                part.y_raw_domain,
                raw_pred,
                labels=labels,
                average="macro",
                zero_division=0,
            )
            raw_metric_rows.append({
                "feature_variant": variant,
                "split_name": part_name,
                "macro_f1": float(score),
                "n": int(len(part)),
                "support": dict(Counter(part.y_raw_domain)),
                "train_classes": raw_classes,
            })

    metrics_df = pd.DataFrame(metric_rows)
    preds_df = pd.DataFrame(pred_rows)
    raw_df = pd.DataFrame(raw_metric_rows)

    metrics_df.assign(details=metrics_df.details.map(json.dumps)).to_csv(out / "metrics.csv", index=False)
    preds_df.to_csv(out / "predictions.csv.gz", index=False, compression="gzip")
    raw_df.assign(
        support=raw_df.support.map(json.dumps),
        train_classes=raw_df.train_classes.map(json.dumps),
    ).to_csv(out / "raw_domain_metrics.csv", index=False)

    test_preds = {
        v: preds_df[
            (preds_df.feature_variant == v)
            & (preds_df.split_name == "test")
        ][["training_example_id", "person_id", "y_true", "y_pred"]]
        for v in VARIANTS
    }
    comparisons = {
        "history_plus_bazi_minus_history": r2.clustered_bootstrap_delta(
            test_preds["history_plus_bazi_v1"], test_preds["history_reality_v1"]
        ),
        "bazi_minus_raw_calendar": r2.clustered_bootstrap_delta(
            test_preds["bazi_objective_only_v1"], test_preds["raw_birth_calendar_v1"]
        ),
        "bazi_minus_placebo": r2.clustered_bootstrap_delta(
            test_preds["bazi_objective_only_v1"], test_preds["bazi_decade_shuffle_placebo_v1"]
        ),
    }

    test_table = metrics_df[metrics_df.split_name == "test"].copy()
    summary = {
        "round": "final-v1-round3",
        "protocol_key": PROTOCOL_KEY,
        "scenario": scenario,
        "dataset_id": r2.DATASET_ID,
        "dataset_fingerprint": r2.DATASET_FINGERPRINT,
        "placebo_mapping_fingerprint": r2.PLACEBO_FINGERPRINT,
        "seed": r2.SEED,
        "row_count": int(len(df)),
        "person_count": int(df.person_id.nunique()),
        "split_counts": {k: int(v) for k, v in split_counts.items()},
        "split_people": {
            k: int(df[df.split_name == k].person_id.nunique())
            for k in ["train", "validation", "test"]
        },
        "target_counts": {k: int(v) for k, v in Counter(df.y_class_4).items()},
        "frozen_config": FROZEN_CFG,
        "no_hyperparameter_selection": True,
        "test_metrics": test_table[[
            "model_family", "feature_variant", "n", "accuracy", "balanced_accuracy", "macro_f1",
            "log_loss", "brier_multiclass", "ece_10bin"
        ]].to_dict(orient="records"),
        "raw_domain_test_metrics": raw_df[raw_df.split_name == "test"][[
            "feature_variant", "n", "macro_f1"
        ]].to_dict(orient="records"),
        "paired_cluster_bootstrap": comparisons,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "model_manifest": model_manifest,
        "notes": [
            "Round 2 hgb_small is frozen; no Round 3 hyperparameter selection occurred.",
            "Validation is diagnostic only and did not alter the model configuration.",
            "Balanced sample weights are derived from each scenario training partition only.",
            "Scenario-specific matched placebo donor maps are used.",
            "Bootstrap confidence intervals resample people, preserving within-person cutoff clustering.",
        ],
    }

    (out / "round3_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "model_manifest.json").write_text(
        json.dumps(model_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    checksums = {}
    for p in sorted(out.rglob("*")):
        if p.is_file():
            checksums[str(p.relative_to(out))] = r2.file_sha256(p)
    (out / "SHA256SUMS.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
