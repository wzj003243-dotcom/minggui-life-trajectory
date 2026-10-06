"""MingGui final v1 — benchmark round 3.

Preregistered out-of-domain benchmark.

No hyperparameter selection is performed here. The model capacity is the
Round-2 validation-selected hgb_small configuration, reused unchanged for:
- forward_era_v1
- geo_us_holdout_v1
- geo_france_holdout_v1
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

from benchmark_final_v1_round2 import (
    DATASET_FINGERPRINT,
    DATASET_ID,
    PLACEBO_FINGERPRINT,
    SEED,
    VARIANTS,
    CLASSES,
    aligned_probabilities,
    clustered_bootstrap_delta,
    feature_columns,
    file_sha256,
    flatten_rows,
    make_model,
    metrics,
)

PROTOCOL_KEY = "next-canonical-domain-ood-round3-v1"
SCENARIOS = ["forward_era_v1", "geo_us_holdout_v1", "geo_france_holdout_v1"]
FIXED_CONFIG = {
    "key": "hgb_small",
    "learning_rate": 0.05,
    "max_iter": 250,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 30,
    "l2_regularization": 2.0,
}


def load_scenario(root: Path, scenario: str) -> pd.DataFrame:
    records = []
    for p in sorted((root / scenario).glob("chunk-*.json")):
        rows = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{p} is not a row array")
        records.extend(rows)
    if len(records) != 7465:
        raise ValueError(f"{scenario}: expected 7465 classification rows, got {len(records)}")
    df = flatten_rows(records).sort_values("training_example_id").reset_index(drop=True)
    if set(df.split_name.unique()) != {"train", "validation", "test"}:
        raise ValueError(f"{scenario}: bad splits {df.split_name.value_counts().to_dict()}")
    return df


def fit_fixed(df: pd.DataFrame, variant: str):
    work = df.copy()
    if variant == "bazi_decade_shuffle_placebo_v1":
        work = work[work.placebo_eligible].copy()
    train = work[work.split_name == "train"].copy()
    num, cat = feature_columns(work, variant)
    cols = num + cat
    model = make_model(num, cat, FIXED_CONFIG)
    weights = compute_sample_weight(class_weight="balanced", y=train.y_class_4)
    model.fit(train[cols], train.y_class_4, clf__sample_weight=weights)
    return model, num, cat, work


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("out_dir")
    args = ap.parse_args()

    inp = Path(args.input_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "models").mkdir(exist_ok=True)

    metric_rows = []
    raw_metric_rows = []
    pred_rows = []
    model_manifest = {}
    scenario_summaries = {}
    comparisons = {}

    for scenario in SCENARIOS:
        df = load_scenario(inp, scenario)
        split_counts = {k: int(v) for k, v in df.groupby("split_name").size().to_dict().items()}
        split_people = {
            s: int(df[df.split_name == s].person_id.nunique())
            for s in ["train", "validation", "test"]
        }
        scenario_summaries[scenario] = {
            "rows": int(len(df)),
            "people": int(df.person_id.nunique()),
            "split_counts": split_counts,
            "split_people": split_people,
            "test_target_counts": {
                k: int(v)
                for k, v in Counter(df[df.split_name == "test"].y_class_4).items()
            },
        }
        model_manifest[scenario] = {}

        for variant in VARIANTS:
            model, num, cat, work = fit_fixed(df, variant)
            cols = num + cat
            train = work[work.split_name == "train"].copy()
            val = work[work.split_name == "validation"].copy()
            test = work[work.split_name == "test"].copy()

            model_dir = out / "models" / scenario
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / f"{variant}.joblib"
            joblib.dump(model, model_path)

            transformed_dim = int(model.named_steps["pre"].transform(train[cols].head(1)).shape[1])
            model_manifest[scenario][variant] = {
                "config": FIXED_CONFIG,
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
                pred = model.predict(part[cols])
                prob = aligned_probabilities(model, part, cols)
                met = metrics(part.y_class_4, pred, prob)
                metric_rows.append({
                    "scenario_key": scenario,
                    "model_family": "hist_gradient_boosting",
                    "feature_variant": variant,
                    "split_name": part_name,
                    **{k: v for k, v in met.items() if k != "per_class"},
                    "details": met["per_class"],
                })
                for i, (_, row) in enumerate(part.iterrows()):
                    pred_rows.append({
                        "scenario_key": scenario,
                        "model_family": "hist_gradient_boosting",
                        "feature_variant": variant,
                        "training_example_id": int(row.training_example_id),
                        "person_id": int(row.person_id),
                        "split_name": part_name,
                        "y_true": row.y_class_4,
                        "y_pred": pred[i],
                        **{f"p_{c}": float(prob[i, j]) for j, c in enumerate(CLASSES)},
                    })

            # Raw-domain diagnostic, same fixed capacity and train-only balancing.
            raw_classes = sorted(train.y_raw_domain.unique())
            raw_model = make_model(num, cat, FIXED_CONFIG)
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
                    "scenario_key": scenario,
                    "feature_variant": variant,
                    "split_name": part_name,
                    "macro_f1": float(score),
                    "n": int(len(part)),
                    "support": dict(Counter(part.y_raw_domain)),
                    "train_classes": raw_classes,
                })

        scenario_preds = pd.DataFrame(pred_rows)
        scenario_preds = scenario_preds[
            (scenario_preds.scenario_key == scenario)
            & (scenario_preds.split_name == "test")
        ]
        test_preds = {
            v: scenario_preds[
                scenario_preds.feature_variant == v
            ][["training_example_id", "person_id", "y_true", "y_pred"]]
            for v in VARIANTS
        }
        comparisons[scenario] = {
            "history_plus_bazi_minus_history": clustered_bootstrap_delta(
                test_preds["history_plus_bazi_v1"],
                test_preds["history_reality_v1"],
            ),
            "bazi_minus_raw_calendar": clustered_bootstrap_delta(
                test_preds["bazi_objective_only_v1"],
                test_preds["raw_birth_calendar_v1"],
            ),
            "bazi_minus_placebo": clustered_bootstrap_delta(
                test_preds["bazi_objective_only_v1"],
                test_preds["bazi_decade_shuffle_placebo_v1"],
            ),
        }

    metrics_df = pd.DataFrame(metric_rows)
    raw_df = pd.DataFrame(raw_metric_rows)
    preds_df = pd.DataFrame(pred_rows)

    metrics_df.assign(details=metrics_df.details.map(json.dumps)).to_csv(
        out / "metrics.csv", index=False
    )
    raw_df.assign(
        support=raw_df.support.map(json.dumps),
        train_classes=raw_df.train_classes.map(json.dumps),
    ).to_csv(out / "raw_domain_metrics.csv", index=False)
    preds_df.to_csv(out / "predictions.csv.gz", index=False, compression="gzip")

    test_metrics = metrics_df[metrics_df.split_name == "test"][
        [
            "scenario_key",
            "model_family",
            "feature_variant",
            "n",
            "accuracy",
            "balanced_accuracy",
            "macro_f1",
            "log_loss",
            "brier_multiclass",
            "ece_10bin",
        ]
    ].to_dict(orient="records")

    raw_test_metrics = raw_df[raw_df.split_name == "test"][
        ["scenario_key", "feature_variant", "n", "macro_f1"]
    ].to_dict(orient="records")

    summary = {
        "round": "final-v1-round3",
        "protocol_key": PROTOCOL_KEY,
        "dataset_id": DATASET_ID,
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "placebo_mapping_fingerprint": PLACEBO_FINGERPRINT,
        "seed": SEED,
        "fixed_config": FIXED_CONFIG,
        "fixed_config_source": "Round 2 validation-only selected hgb_small",
        "no_round3_hyperparameter_selection": True,
        "scenarios": scenario_summaries,
        "test_metrics": test_metrics,
        "raw_domain_test_metrics": raw_test_metrics,
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
            "No Round 3 holdout was used for hyperparameter selection.",
            "The exact Round 2 hgb_small configuration was reused unchanged.",
            "Balanced sample weights were computed from each scenario train partition only.",
            "Placebo donor mappings are scenario-specific and frozen before modeling.",
            "Bootstrap confidence intervals resample people.",
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
            checksums[str(p.relative_to(out))] = file_sha256(p)
    (out / "SHA256SUMS.json").write_text(
        json.dumps(checksums, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
