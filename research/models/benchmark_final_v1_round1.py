"""MingGui final v1 — benchmark round 1.

Frozen protocol:
- dataset: next-observed-canonical-event-domain / v1.0-final
- split: person_hash_v1
- target: 4-class next documented canonical event domain
- models: train-prior sanity baseline + multinomial logistic regression
- feature variants: history, raw calendar, BaZi, history+BaZi, shuffled-BaZi placebo

This script consumes JSON chunks exported from the frozen model-facing view.
It does not reconstruct events, labels, splits, or placebo mappings.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATASET_ID = "8261f970-adc3-4f9a-8043-9e0f6cb90be8"
DATASET_FINGERPRINT = "a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888"
PLACEBO_FINGERPRINT = "3010d4188445645271ca771980f8947d20f96362f96f6b286e256610887cdd0e"
SCENARIO = "person_hash_v1"
SEED = 20261006
CLASSES = ["career", "other", "recognition", "relationship"]
VARIANTS = [
    "history_reality_v1",
    "raw_birth_calendar_v1",
    "bazi_objective_only_v1",
    "history_plus_bazi_v1",
    "bazi_decade_shuffle_placebo_v1",
]


def get(d, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def flatten_rows(records: list[dict]) -> pd.DataFrame:
    all_domains = sorted({
        k
        for r in records
        for k in (get(r, "x", "history", "summary", "domain_counts", default={}) or {}).keys()
    })
    bazi_numeric = sorted({
        k
        for r in records
        for k in (get(r, "x", "objective_bazi_features", default={}) or {}).keys()
    })
    pillar_keys = sorted({
        k
        for r in records
        for k in (get(r, "x", "four_pillars", default={}) or {}).keys()
    })
    quality_keys = sorted({
        k
        for r in records
        for k in (get(r, "x", "bazi_quality_flags", default={}) or {}).keys()
    })

    rows = []
    for r in records:
        x = r["x"]
        bg = x.get("background") or {}
        cal = x.get("raw_birth_calendar") or {}
        hist = x.get("history") or {}
        hsum = hist.get("summary") or {}
        hdom = hsum.get("domain_counts") or {}
        bazi = x.get("objective_bazi_features") or {}
        pillars = x.get("four_pillars") or {}
        quality = x.get("bazi_quality_flags") or {}
        dbazi = r.get("donor_bazi_features") or {}
        dpillars = r.get("donor_four_pillars") or {}
        dquality = r.get("donor_bazi_quality_flags") or {}

        z = {
            "training_example_id": int(r["training_example_id"]),
            "person_id": int(r["person_id"]),
            "wikidata_id": r["wikidata_id"],
            "cutoff_age": int(r["cutoff_age"]),
            "split_name": r["split_name"],
            "fold": r.get("fold"),
            "y_class_4": r["y_class_4"],
            "y_raw_domain": r["y_raw_domain"],
            "placebo_eligible": bool(r.get("placebo_eligible")),
            "donor_person_id": r.get("donor_person_id"),
            "gender": bg.get("gender"),
            "birth_year": bg.get("birth_year"),
            "birth_country_normalized": bg.get("birth_country_normalized"),
            "birth_geo_group": bg.get("birth_geo_group"),
            "birth_time_known": bg.get("birth_time_known"),
            "birth_month": cal.get("birth_month"),
            "birth_day": cal.get("birth_day"),
            "birth_hour": cal.get("birth_hour"),
            "birth_minute": cal.get("birth_minute"),
            "history_canonical_event_count": hist.get("canonical_event_count", 0),
            "history_raw_event_count": hist.get("raw_event_count", 0),
            "history_domain_count": hist.get("domain_count", 0),
            "history_source_family_count": hist.get("source_family_count", 0),
            "history_life_stage_count": hist.get("life_stage_count", 0),
        }
        for d in all_domains:
            z[f"history_domain__{d}"] = hdom.get(d, 0)
        for k in bazi_numeric:
            z[f"bazi__{k}"] = bazi.get(k)
            z[f"placebo_bazi__{k}"] = dbazi.get(k)
        for k in pillar_keys:
            z[f"pillar__{k}"] = pillars.get(k)
            z[f"placebo_pillar__{k}"] = dpillars.get(k)
        for k in quality_keys:
            z[f"bazi_quality__{k}"] = quality.get(k)
            z[f"placebo_bazi_quality__{k}"] = dquality.get(k)
        rows.append(z)
    return pd.DataFrame(rows)


def feature_columns(df: pd.DataFrame, variant: str) -> tuple[list[str], list[str]]:
    hist_num = [
        "cutoff_age", "birth_year",
        "history_canonical_event_count", "history_raw_event_count",
        "history_domain_count", "history_source_family_count", "history_life_stage_count",
    ] + sorted(c for c in df.columns if c.startswith("history_domain__"))
    hist_cat = ["gender", "birth_country_normalized", "birth_geo_group"]

    raw_num = ["birth_year", "birth_month", "birth_day", "birth_hour", "birth_minute", "cutoff_age"]
    raw_cat = ["gender", "birth_country_normalized"]

    bazi_num = ["cutoff_age"] + sorted(c for c in df.columns if c.startswith("bazi__")) + sorted(
        c for c in df.columns if c.startswith("bazi_quality__")
    )
    bazi_cat = sorted(c for c in df.columns if c.startswith("pillar__"))

    placebo_num = ["cutoff_age"] + sorted(c for c in df.columns if c.startswith("placebo_bazi__")) + sorted(
        c for c in df.columns if c.startswith("placebo_bazi_quality__")
    )
    placebo_cat = sorted(c for c in df.columns if c.startswith("placebo_pillar__"))

    if variant == "history_reality_v1":
        return hist_num, hist_cat
    if variant == "raw_birth_calendar_v1":
        return raw_num, raw_cat
    if variant == "bazi_objective_only_v1":
        return bazi_num, bazi_cat
    if variant == "history_plus_bazi_v1":
        return list(dict.fromkeys(hist_num + bazi_num)), list(dict.fromkeys(hist_cat + bazi_cat))
    if variant == "bazi_decade_shuffle_placebo_v1":
        return placebo_num, placebo_cat
    raise KeyError(variant)


def make_model(num: list[str], cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline([
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]),
                num,
            ),
            (
                "cat",
                Pipeline([
                    ("impute", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore")),
                ]),
                cat,
            ),
        ],
        remainder="drop",
    )
    clf = LogisticRegression(
        max_iter=5000,
        class_weight="balanced",
        C=1.0,
        solver="lbfgs",
        random_state=SEED,
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def aligned_probabilities(model: Pipeline, frame: pd.DataFrame, cols: list[str], classes: list[str]) -> np.ndarray:
    p = model.predict_proba(frame[cols])
    mc = list(model.named_steps["clf"].classes_)
    out = np.zeros((len(frame), len(classes)), dtype=float)
    for j, c in enumerate(classes):
        if c in mc:
            out[:, j] = p[:, mc.index(c)]
    return out


def multiclass_brier(y: pd.Series, p: np.ndarray, classes: list[str]) -> float:
    idx = {c: i for i, c in enumerate(classes)}
    onehot = np.zeros_like(p)
    for i, v in enumerate(y):
        if v in idx:
            onehot[i, idx[v]] = 1.0
    return float(np.mean(np.sum((p - onehot) ** 2, axis=1)))


def ece_top_label(y: pd.Series, pred: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    conf = p.max(axis=1)
    correct = (pred == y.to_numpy()).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    total = len(y)
    val = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if mask.any():
            val += mask.sum() / total * abs(correct[mask].mean() - conf[mask].mean())
    return float(val)


def metrics(y: pd.Series, pred: np.ndarray, p: np.ndarray, classes: list[str]) -> dict:
    pr, rc, f1, sup = precision_recall_fscore_support(
        y, pred, labels=classes, zero_division=0
    )
    return {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=classes, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y, p, labels=classes)),
        "brier_multiclass": multiclass_brier(y, p, classes),
        "ece_10bin": ece_top_label(y, pred, p),
        "per_class": {
            c: {
                "precision": float(pr[i]),
                "recall": float(rc[i]),
                "f1": float(f1[i]),
                "support": int(sup[i]),
            }
            for i, c in enumerate(classes)
        },
    }


def prior_predictions(train_y: pd.Series, part: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    counts = train_y.value_counts()
    probs = np.array([counts.get(c, 0) / len(train_y) for c in CLASSES], dtype=float)
    p = np.repeat(probs[None, :], len(part), axis=0)
    pred = np.array([CLASSES[int(np.argmax(probs))]] * len(part), dtype=object)
    return pred, p


def clustered_bootstrap_delta(
    a: pd.DataFrame,
    b: pd.DataFrame,
    reps: int = 1000,
    seed: int = SEED,
) -> dict:
    merged = a.merge(
        b,
        on=["training_example_id", "person_id", "y_true"],
        suffixes=("_a", "_b"),
        how="inner",
    )
    people = np.array(sorted(merged.person_id.unique()))
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(reps):
        sampled = rng.choice(people, size=len(people), replace=True)
        parts = []
        for pid in sampled:
            parts.append(merged[merged.person_id == pid])
        boot = pd.concat(parts, ignore_index=True)
        fa = f1_score(boot.y_true, boot.y_pred_a, labels=CLASSES, average="macro", zero_division=0)
        fb = f1_score(boot.y_true, boot.y_pred_b, labels=CLASSES, average="macro", zero_division=0)
        deltas.append(fa - fb)
    q = np.quantile(deltas, [0.025, 0.5, 0.975])
    observed = (
        f1_score(merged.y_true, merged.y_pred_a, labels=CLASSES, average="macro", zero_division=0)
        - f1_score(merged.y_true, merged.y_pred_b, labels=CLASSES, average="macro", zero_division=0)
    )
    return {
        "paired_rows": int(len(merged)),
        "paired_people": int(merged.person_id.nunique()),
        "delta_macro_f1": float(observed),
        "bootstrap_mean": float(np.mean(deltas)),
        "ci95_low": float(q[0]),
        "bootstrap_median": float(q[1]),
        "ci95_high": float(q[2]),
        "positive_fraction": float(np.mean(np.array(deltas) > 0)),
        "bootstrap_unit": "person",
        "reps": reps,
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("out_dir")
    args = ap.parse_args()
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

    df = flatten_rows(records).sort_values("training_example_id").reset_index(drop=True)
    split_counts = df.groupby("split_name").size().to_dict()
    if set(split_counts) != {"train", "validation", "test"}:
        raise ValueError(split_counts)

    train = df[df.split_name == "train"].copy()
    val = df[df.split_name == "validation"].copy()
    test = df[df.split_name == "test"].copy()

    metric_rows = []
    pred_rows = []
    raw_metric_rows = []
    model_manifest = {}

    # Train-prior sanity baseline.
    for part_name, part in [("validation", val), ("test", test)]:
        pred, prob = prior_predictions(train.y_class_4, part)
        met = metrics(part.y_class_4, pred, prob, CLASSES)
        metric_rows.append({"model_family": "majority_prior", "feature_variant": "none", "split_name": part_name, **{k:v for k,v in met.items() if k != "per_class"}, "details": met["per_class"]})
        for i, (_, row) in enumerate(part.iterrows()):
            pred_rows.append({
                "model_family": "majority_prior",
                "feature_variant": "none",
                "training_example_id": int(row.training_example_id),
                "person_id": int(row.person_id),
                "split_name": part_name,
                "y_true": row.y_class_4,
                "y_pred": pred[i],
                **{f"p_{c}": float(prob[i,j]) for j,c in enumerate(CLASSES)},
            })

    # Logistic models for all frozen feature variants.
    fitted = {}
    for variant in VARIANTS:
        work = df.copy()
        if variant == "bazi_decade_shuffle_placebo_v1":
            work = work[work.placebo_eligible].copy()
        tr = work[work.split_name == "train"].copy()
        va = work[work.split_name == "validation"].copy()
        te = work[work.split_name == "test"].copy()
        num, cat = feature_columns(work, variant)
        cols = num + cat

        model = make_model(num, cat)
        model.fit(tr[cols], tr.y_class_4)
        fitted[variant] = model
        model_path = out / "models" / f"{variant}.joblib"
        joblib.dump(model, model_path)

        model_manifest[variant] = {
            "train_rows": int(len(tr)),
            "validation_rows": int(len(va)),
            "test_rows": int(len(te)),
            "train_people": int(tr.person_id.nunique()),
            "validation_people": int(va.person_id.nunique()),
            "test_people": int(te.person_id.nunique()),
            "numeric_features": num,
            "categorical_features": cat,
            "model_file": str(model_path.relative_to(out)),
        }

        for part_name, part in [("validation", va), ("test", te)]:
            pred = model.predict(part[cols])
            prob = aligned_probabilities(model, part, cols, CLASSES)
            met = metrics(part.y_class_4, pred, prob, CLASSES)
            metric_rows.append({
                "model_family": "multinomial_logistic",
                "feature_variant": variant,
                "split_name": part_name,
                **{k:v for k,v in met.items() if k != "per_class"},
                "details": met["per_class"],
            })
            for i, (_, row) in enumerate(part.iterrows()):
                pred_rows.append({
                    "model_family": "multinomial_logistic",
                    "feature_variant": variant,
                    "training_example_id": int(row.training_example_id),
                    "person_id": int(row.person_id),
                    "split_name": part_name,
                    "y_true": row.y_class_4,
                    "y_pred": pred[i],
                    **{f"p_{c}": float(prob[i,j]) for j,c in enumerate(CLASSES)},
                })

        # Raw-domain diagnostic uses the same frozen feature columns.
        raw_classes = sorted(tr.y_raw_domain.unique())
        raw_model = make_model(num, cat)
        raw_model.fit(tr[cols], tr.y_raw_domain)
        for part_name, part in [("validation", va), ("test", te)]:
            raw_pred = raw_model.predict(part[cols])
            score = f1_score(
                part.y_raw_domain,
                raw_pred,
                labels=sorted(set(raw_classes) | set(part.y_raw_domain.unique())),
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

    metrics_path = out / "metrics.csv"
    preds_path = out / "predictions.csv.gz"
    raw_path = out / "raw_domain_metrics.csv"
    metrics_df.assign(details=metrics_df.details.map(json.dumps)).to_csv(metrics_path, index=False)
    preds_df.to_csv(preds_path, index=False, compression="gzip")
    raw_df.assign(
        support=raw_df.support.map(json.dumps),
        train_classes=raw_df.train_classes.map(json.dumps),
    ).to_csv(raw_path, index=False)

    test_preds = {
        v: preds_df[
            (preds_df.model_family == "multinomial_logistic")
            & (preds_df.feature_variant == v)
            & (preds_df.split_name == "test")
        ][["training_example_id", "person_id", "y_true", "y_pred"]]
        for v in VARIANTS
    }
    comparisons = {
        "history_plus_bazi_minus_history": clustered_bootstrap_delta(
            test_preds["history_plus_bazi_v1"], test_preds["history_reality_v1"]
        ),
        "bazi_minus_raw_calendar": clustered_bootstrap_delta(
            test_preds["bazi_objective_only_v1"], test_preds["raw_birth_calendar_v1"]
        ),
        "bazi_minus_placebo": clustered_bootstrap_delta(
            test_preds["bazi_objective_only_v1"], test_preds["bazi_decade_shuffle_placebo_v1"]
        ),
    }

    test_table = metrics_df[metrics_df.split_name == "test"].copy()
    summary = {
        "round": "final-v1-round1",
        "dataset_id": DATASET_ID,
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "placebo_mapping_fingerprint": PLACEBO_FINGERPRINT,
        "split_scenario": SCENARIO,
        "seed": SEED,
        "row_count": int(len(df)),
        "person_count": int(df.person_id.nunique()),
        "split_counts": {k:int(v) for k,v in split_counts.items()},
        "target_counts": {k:int(v) for k,v in Counter(df.y_class_4).items()},
        "train_target_counts": {k:int(v) for k,v in Counter(train.y_class_4).items()},
        "test_metrics": test_table[[
            "model_family","feature_variant","n","accuracy","balanced_accuracy","macro_f1",
            "log_loss","brier_multiclass","ece_10bin"
        ]].to_dict(orient="records"),
        "raw_domain_test_metrics": raw_df[raw_df.split_name=="test"][[
            "feature_variant","n","macro_f1"
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
            "No hyperparameter search was performed.",
            "Balanced class weights are learned from the training partition only.",
            "Test was evaluated once after the final-v1 protocol had been frozen.",
            "Placebo singleton decade/split groups are excluded only from the placebo model.",
            "Bootstrap confidence intervals resample people, preserving within-person cutoff clustering.",
        ],
    }

    summary_path = out / "round1_summary.json"
    manifest_path = out / "model_manifest.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(model_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    checksums = {}
    for p in sorted(out.rglob("*")):
        if p.is_file():
            checksums[str(p.relative_to(out))] = file_sha256(p)
    (out / "SHA256SUMS.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
