"""MingGui final v1 — Round 4 censor-aware probabilistic trajectory baseline.

Frozen protocol: discrete-hazard-trajectory-round4-v1

This consumes the immutable v1.0-derived person-period dataset.  It does not
reconstruct source labels from mutable life-event tables.
"""
from __future__ import annotations

import argparse
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
from sklearn.ensemble import HistGradientBoostingClassifier
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

TRAJECTORY_DATASET_ID = "731fa601-9c18-4ce8-9a8a-557ded47395d"
TRAJECTORY_FINGERPRINT = "9e2de5961856ad79ae260cb87fea1028f38b278c74eb3ff7669d94a35cf9f7c3"
SOURCE_DATASET_ID = "8261f970-adc3-4f9a-8043-9e0f6cb90be8"
SOURCE_FINGERPRINT = "a4752568b6145db7629c62b8a68b4a7f5116db79c2628e5e5d4d28b9e76ba888"
PROTOCOL_KEY = "discrete-hazard-trajectory-round4-v1"
SCENARIO = "person_hash_v1"
SEED = 20261006

# Lexicographic order keeps sklearn log_loss class/probability alignment explicit.
CLASSES = ["career", "no_event", "other", "recognition", "relationship"]
EVENT_CLASSES = ["career", "other", "recognition", "relationship"]
HORIZONS = [1, 3, 5, 10, 20]
INTERVALS = [(0, 1), (1, 3), (3, 5), (5, 10), (10, 20)]

VARIANTS = [
    "history_reality_v1",
    "raw_birth_calendar_v1",
    "bazi_objective_only_v1",
    "history_plus_bazi_v1",
    "bazi_decade_shuffle_placebo_v1",
]

HGB_CFG = {
    "key": "hgb_small",
    "learning_rate": 0.05,
    "max_iter": 250,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 30,
    "l2_regularization": 2.0,
}


def get(d, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def read_chunks(directory: Path, prefix: str) -> list[dict]:
    rows: list[dict] = []
    for p in sorted(directory.glob(f"{prefix}-*.json")):
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, list):
            raise ValueError(f"{p} is not a JSON row array")
        rows.extend(obj)
    return rows


def flatten_cutoffs(records: list[dict]) -> pd.DataFrame:
    all_domains = sorted({
        k
        for r in records
        for k in (get(r, "x_features", "history", "summary", "domain_counts", default={}) or {}).keys()
    })
    bazi_numeric = sorted({
        k
        for r in records
        for k in (get(r, "x_features", "objective_bazi_features", default={}) or {}).keys()
    })
    pillar_keys = sorted({
        k
        for r in records
        for k in (get(r, "x_features", "four_pillars", default={}) or {}).keys()
    })
    quality_keys = sorted({
        k
        for r in records
        for k in (get(r, "x_features", "bazi_quality_flags", default={}) or {}).keys()
    })

    out = []
    for r in records:
        x = r.get("x_features") or {}
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
            "source_training_example_id": int(r["source_training_example_id"]),
            "person_id": int(r["person_id"]),
            "wikidata_id": r["wikidata_id"],
            "cutoff_age": int(r["cutoff_age"]),
            "cutoff_date": r["cutoff_date"],
            "source_target_domain": r.get("source_target_domain"),
            "source_target_observable_from": r.get("source_target_observable_from"),
            "source_observation_end_date": r.get("source_observation_end_date"),
            "source_right_censored": bool(r.get("source_right_censored")),
            "split_name": r["split_name"],
            "fold": r.get("fold"),
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
        out.append(z)
    df = pd.DataFrame(out)
    for c in ["cutoff_date", "source_target_observable_from", "source_observation_end_date"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def feature_columns(df: pd.DataFrame, variant: str) -> tuple[list[str], list[str]]:
    interval_num = ["interval_index", "interval_start_year", "interval_end_year", "interval_width_years"]

    hist_num = [
        "cutoff_age",
        "birth_year",
        "history_canonical_event_count",
        "history_raw_event_count",
        "history_domain_count",
        "history_source_family_count",
        "history_life_stage_count",
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
        return list(dict.fromkeys(hist_num + interval_num)), hist_cat
    if variant == "raw_birth_calendar_v1":
        return list(dict.fromkeys(raw_num + interval_num)), raw_cat
    if variant == "bazi_objective_only_v1":
        return list(dict.fromkeys(bazi_num + interval_num)), bazi_cat
    if variant == "history_plus_bazi_v1":
        return list(dict.fromkeys(hist_num + bazi_num + interval_num)), list(dict.fromkeys(hist_cat + bazi_cat))
    if variant == "bazi_decade_shuffle_placebo_v1":
        return list(dict.fromkeys(placebo_num + interval_num)), placebo_cat
    raise KeyError(variant)


def make_logistic(num: list[str], cat: list[str]) -> Pipeline:
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
        class_weight=None,
        C=1.0,
        solver="lbfgs",
        random_state=SEED,
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def make_hgb(num: list[str], cat: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline([("impute", SimpleImputer(strategy="median"))]),
                num,
            ),
            (
                "cat",
                Pipeline([
                    ("impute", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                cat,
            ),
        ],
        remainder="drop",
    )
    clf = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=HGB_CFG["learning_rate"],
        max_iter=HGB_CFG["max_iter"],
        max_leaf_nodes=HGB_CFG["max_leaf_nodes"],
        min_samples_leaf=HGB_CFG["min_samples_leaf"],
        l2_regularization=HGB_CFG["l2_regularization"],
        early_stopping=False,
        random_state=SEED,
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def align_probs(classes, p: np.ndarray) -> np.ndarray:
    out = np.zeros((len(p), len(CLASSES)), dtype=float)
    classes = list(classes)
    for j, c in enumerate(CLASSES):
        if c in classes:
            out[:, j] = p[:, classes.index(c)]
    row_sum = out.sum(axis=1)
    bad = row_sum <= 0
    if bad.any():
        out[bad] = 1.0 / len(CLASSES)
        row_sum = out.sum(axis=1)
    return out / row_sum[:, None]


def model_probs(model: Pipeline, frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    p = model.predict_proba(frame[cols])
    return align_probs(model.named_steps["clf"].classes_, p)


def prior_probs(train: pd.DataFrame, part: pd.DataFrame) -> np.ndarray:
    dist = {}
    global_counts = train.outcome_class.value_counts()
    global_p = np.array([global_counts.get(c, 0) for c in CLASSES], dtype=float)
    global_p /= global_p.sum()
    for idx, g in train.groupby("interval_index"):
        cnt = g.outcome_class.value_counts()
        p = np.array([cnt.get(c, 0) for c in CLASSES], dtype=float)
        p /= p.sum()
        dist[int(idx)] = p
    return np.vstack([dist.get(int(i), global_p) for i in part.interval_index])


def multiclass_brier(y: pd.Series, p: np.ndarray) -> float:
    idx = {c: i for i, c in enumerate(CLASSES)}
    onehot = np.zeros_like(p)
    for i, v in enumerate(y):
        onehot[i, idx[v]] = 1.0
    return float(np.mean(np.sum((p - onehot) ** 2, axis=1)))


def ece_top_label(y: pd.Series, pred: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    conf = p.max(axis=1)
    correct = (pred == y.to_numpy()).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    val = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if mask.any():
            val += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(val)


def conditional_event_metrics(y: pd.Series, p: np.ndarray) -> dict:
    mask = y.to_numpy() != "no_event"
    if not mask.any():
        return {"n_event": 0, "conditional_domain_log_loss": None, "conditional_domain_macro_f1": None}
    event_idx = [CLASSES.index(c) for c in EVENT_CLASSES]
    ep = p[mask][:, event_idx]
    sums = ep.sum(axis=1)
    zero = sums <= 1e-15
    if zero.any():
        ep[zero] = 1.0 / len(EVENT_CLASSES)
        sums = ep.sum(axis=1)
    ep = ep / sums[:, None]
    ey = y.to_numpy()[mask]
    pred = np.array(EVENT_CLASSES, dtype=object)[np.argmax(ep, axis=1)]
    return {
        "n_event": int(mask.sum()),
        "conditional_domain_log_loss": float(log_loss(ey, ep, labels=EVENT_CLASSES)),
        "conditional_domain_macro_f1": float(
            f1_score(ey, pred, labels=EVENT_CLASSES, average="macro", zero_division=0)
        ),
    }


def interval_metrics(y: pd.Series, p: np.ndarray) -> dict:
    pred = np.array(CLASSES, dtype=object)[np.argmax(p, axis=1)]
    event_true = (y.to_numpy() != "no_event").astype(float)
    event_p = 1.0 - p[:, CLASSES.index("no_event")]
    pr, rc, f1, sup = precision_recall_fscore_support(y, pred, labels=CLASSES, zero_division=0)
    out = {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=CLASSES, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y, p, labels=CLASSES)),
        "brier_multiclass": multiclass_brier(y, p),
        "ece_10bin": ece_top_label(y, pred, p),
        "event_vs_no_event_brier": float(np.mean((event_p - event_true) ** 2)),
        "per_class": {
            c: {
                "precision": float(pr[i]),
                "recall": float(rc[i]),
                "f1": float(f1[i]),
                "support": int(sup[i]),
            }
            for i, c in enumerate(CLASSES)
        },
    }
    out.update(conditional_event_metrics(y, p))
    return out


def map_domain(domain) -> str:
    if domain in ("career", "recognition", "relationship"):
        return str(domain)
    return "other"


def expand_all_intervals(cutoffs: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for idx, (start, end) in enumerate(INTERVALS):
        x = cutoffs.copy()
        x["interval_index"] = idx
        x["interval_start_year"] = start
        x["interval_end_year"] = end
        x["interval_width_years"] = end - start
        frames.append(x)
    return pd.concat(frames, ignore_index=True)


def compose_horizon_predictions(
    cutoff_part: pd.DataFrame,
    all_interval_part: pd.DataFrame,
    p: np.ndarray,
    model_family: str,
    feature_variant: str,
) -> pd.DataFrame:
    work = all_interval_part[
        ["source_training_example_id", "person_id", "split_name", "interval_index"]
    ].copy()
    for j, c in enumerate(CLASSES):
        work[f"p_{c}"] = p[:, j]

    rows = []
    by_id = {int(k): g.sort_values("interval_index") for k, g in work.groupby("source_training_example_id")}
    no_idx = CLASSES.index("no_event")

    for _, src in cutoff_part.iterrows():
        sid = int(src.source_training_example_id)
        g = by_id[sid]
        survival = 1.0
        cif = {c: 0.0 for c in EVENT_CLASSES}

        target_date = src.source_target_observable_from
        obs_end = src.source_observation_end_date
        target_domain = src.source_target_domain
        cutoff_date = src.cutoff_date

        for _, r in g.iterrows():
            idx = int(r.interval_index)
            probs = np.array([float(r[f"p_{c}"]) for c in CLASSES], dtype=float)
            for c in EVENT_CLASSES:
                cif[c] += survival * probs[CLASSES.index(c)]
            survival *= probs[no_idx]
            horizon = INTERVALS[idx][1]

            horizon_date = cutoff_date + pd.DateOffset(years=horizon)
            evaluable = False
            y_true = None
            if pd.notna(target_date):
                evaluable = True
                y_true = map_domain(target_domain) if target_date <= horizon_date else "no_event"
            elif pd.notna(obs_end) and obs_end >= horizon_date:
                evaluable = True
                y_true = "no_event"

            row = {
                "model_family": model_family,
                "feature_variant": feature_variant,
                "source_training_example_id": sid,
                "person_id": int(src.person_id),
                "split_name": src.split_name,
                "horizon_years": horizon,
                "evaluable": bool(evaluable),
                "y_true": y_true,
                "survival_probability": float(survival),
            }
            total = survival + sum(cif.values())
            if total <= 0:
                total = 1.0
            row["p_no_event"] = float(survival / total)
            for c in EVENT_CLASSES:
                row[f"p_{c}"] = float(cif[c] / total)
            rows.append(row)
    return pd.DataFrame(rows)


def horizon_metrics(hdf: pd.DataFrame) -> list[dict]:
    rows = []
    for (model_family, feature_variant, split_name, horizon), g0 in hdf.groupby(
        ["model_family", "feature_variant", "split_name", "horizon_years"]
    ):
        g = g0[g0.evaluable].copy()
        if g.empty:
            continue
        p = np.column_stack([g[f"p_{c}"].to_numpy(float) for c in CLASSES])
        y = g.y_true.astype(str)
        met = interval_metrics(y, p)
        rows.append({
            "model_family": model_family,
            "feature_variant": feature_variant,
            "split_name": split_name,
            "horizon_years": int(horizon),
            **{k: v for k, v in met.items() if k != "per_class"},
            "details": met["per_class"],
        })
    return rows


def bootstrap_pair(a: pd.DataFrame, b: pd.DataFrame, reps: int = 1000) -> dict:
    key = ["person_period_id", "person_id", "y_true"]
    m = a.merge(b, on=key, suffixes=("_a", "_b"), how="inner")
    idx = {c: i for i, c in enumerate(CLASSES)}
    yi = np.array([idx[v] for v in m.y_true], dtype=int)
    pa = np.column_stack([m[f"p_{c}_a"].to_numpy(float) for c in CLASSES])
    pb = np.column_stack([m[f"p_{c}_b"].to_numpy(float) for c in CLASSES])
    eps = 1e-15
    loss_a = -np.log(np.clip(pa[np.arange(len(m)), yi], eps, 1.0))
    loss_b = -np.log(np.clip(pb[np.arange(len(m)), yi], eps, 1.0))
    oh = np.zeros_like(pa)
    oh[np.arange(len(m)), yi] = 1.0
    brier_a = np.sum((pa - oh) ** 2, axis=1)
    brier_b = np.sum((pb - oh) ** 2, axis=1)

    tmp = pd.DataFrame({
        "person_id": m.person_id.to_numpy(),
        "loss_diff": loss_a - loss_b,
        "brier_diff": brier_a - brier_b,
    })
    agg = tmp.groupby("person_id").agg(
        loss_sum=("loss_diff", "sum"),
        brier_sum=("brier_diff", "sum"),
        n=("loss_diff", "size"),
    )
    people = agg.index.to_numpy()
    rng = np.random.default_rng(SEED)
    dl, db = [], []
    arr = agg[["loss_sum", "brier_sum", "n"]].to_numpy(float)
    pos = {pid: i for i, pid in enumerate(people)}
    for _ in range(reps):
        sampled = rng.choice(people, size=len(people), replace=True)
        ids = np.array([pos[x] for x in sampled], dtype=int)
        sums = arr[ids].sum(axis=0)
        dl.append(sums[0] / sums[2])
        db.append(sums[1] / sums[2])
    dl = np.asarray(dl)
    db = np.asarray(db)
    observed_loss = float((loss_a - loss_b).mean())
    observed_brier = float((brier_a - brier_b).mean())
    return {
        "paired_rows": int(len(m)),
        "paired_people": int(m.person_id.nunique()),
        "delta_log_loss": observed_loss,
        "delta_log_loss_ci95": [float(x) for x in np.quantile(dl, [0.025, 0.975])],
        "delta_log_loss_negative_fraction": float(np.mean(dl < 0)),
        "delta_brier": observed_brier,
        "delta_brier_ci95": [float(x) for x in np.quantile(db, [0.025, 0.975])],
        "delta_brier_negative_fraction": float(np.mean(db < 0)),
        "bootstrap_unit": "person",
        "reps": reps,
        "interpretation": "negative delta favors the first-named model",
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

    cutoff_records = read_chunks(inp, "cutoffs")
    period_records = read_chunks(inp, "periods")
    if len(cutoff_records) != 13064:
        raise ValueError(f"expected 13064 cutoff rows, got {len(cutoff_records)}")
    if len(period_records) != 52427:
        raise ValueError(f"expected 52427 person-period rows, got {len(period_records)}")

    cutoffs = flatten_cutoffs(cutoff_records)
    periods = pd.DataFrame(period_records)
    periods["person_period_id"] = periods["id"].astype(int)
    periods["source_training_example_id"] = periods["source_training_example_id"].astype(int)
    periods["person_id"] = periods["person_id"].astype(int)
    periods["interval_index"] = periods["interval_index"].astype(int)
    periods["interval_start_year"] = periods["interval_start_year"].astype(int)
    periods["interval_end_year"] = periods["interval_end_year"].astype(int)
    periods["interval_width_years"] = periods["interval_width_years"].astype(int)

    if set(periods.outcome_class.unique()) - set(CLASSES):
        raise ValueError(f"unexpected outcomes: {set(periods.outcome_class.unique()) - set(CLASSES)}")

    data = periods.merge(
        cutoffs,
        on=["source_training_example_id", "person_id", "cutoff_age"],
        how="left",
        validate="many_to_one",
    )
    if data.split_name.isna().any():
        raise ValueError("period rows missing split after cutoff join")

    split_counts = {
        k: int(v)
        for k, v in data.groupby("split_name").size().to_dict().items()
    }
    cutoff_split_counts = {
        k: int(v)
        for k, v in cutoffs.groupby("split_name").size().to_dict().items()
    }

    interval_metric_rows = []
    interval_prediction_rows = []
    horizon_frames = []
    manifests = {}

    # Empirical interval prior baseline.
    train = data[data.split_name == "train"].copy()
    prior_manifest = {}
    for idx, g in train.groupby("interval_index"):
        cnt = g.outcome_class.value_counts()
        prior_manifest[str(int(idx))] = {
            c: float(cnt.get(c, 0) / len(g)) for c in CLASSES
        }
    (out / "interval_prior.json").write_text(
        json.dumps(prior_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for split in ["validation", "test"]:
        part = data[data.split_name == split].copy()
        p = prior_probs(train, part)
        pred = np.array(CLASSES, dtype=object)[np.argmax(p, axis=1)]
        met = interval_metrics(part.outcome_class, p)
        interval_metric_rows.append({
            "model_family": "interval_prior",
            "feature_variant": "interval_time_only_prior_v1",
            "split_name": split,
            **{k: v for k, v in met.items() if k != "per_class"},
            "details": met["per_class"],
        })
        for i, (_, row) in enumerate(part.iterrows()):
            interval_prediction_rows.append({
                "model_family": "interval_prior",
                "feature_variant": "interval_time_only_prior_v1",
                "person_period_id": int(row.person_period_id),
                "source_training_example_id": int(row.source_training_example_id),
                "person_id": int(row.person_id),
                "split_name": split,
                "interval_index": int(row.interval_index),
                "y_true": row.outcome_class,
                "y_pred": pred[i],
                **{f"p_{c}": float(p[i, j]) for j, c in enumerate(CLASSES)},
            })

        cutoff_part = cutoffs[cutoffs.split_name == split].copy()
        grid = expand_all_intervals(cutoff_part)
        pp = prior_probs(train, grid)
        horizon_frames.append(
            compose_horizon_predictions(
                cutoff_part, grid, pp, "interval_prior", "interval_time_only_prior_v1"
            )
        )

    # Fixed logistic and HGB models, no hyperparameter selection.
    for family in ["multinomial_logistic", "hist_gradient_boosting"]:
        for variant in VARIANTS:
            work = data.copy()
            cutoff_work = cutoffs.copy()
            if variant == "bazi_decade_shuffle_placebo_v1":
                work = work[work.placebo_eligible].copy()
                cutoff_work = cutoff_work[cutoff_work.placebo_eligible].copy()

            tr = work[work.split_name == "train"].copy()
            num, cat = feature_columns(work, variant)
            cols = num + cat
            model = make_logistic(num, cat) if family == "multinomial_logistic" else make_hgb(num, cat)
            model.fit(tr[cols], tr.outcome_class)

            model_path = out / "models" / f"{family}__{variant}.joblib"
            joblib.dump(model, model_path)
            transformed_dim = int(model.named_steps["pre"].transform(tr[cols].head(1)).shape[1])
            manifests[f"{family}|{variant}"] = {
                "model_family": family,
                "feature_variant": variant,
                "train_rows": int(len(tr)),
                "train_people": int(tr.person_id.nunique()),
                "numeric_features": num,
                "categorical_features": cat,
                "transformed_feature_dim": transformed_dim,
                "model_file": str(model_path.relative_to(out)),
                "class_weight": None,
                "hgb_config": HGB_CFG if family == "hist_gradient_boosting" else None,
                "logistic_config": {"C": 1.0, "solver": "lbfgs", "max_iter": 5000} if family == "multinomial_logistic" else None,
            }

            for split in ["validation", "test"]:
                part = work[work.split_name == split].copy()
                p = model_probs(model, part, cols)
                pred = np.array(CLASSES, dtype=object)[np.argmax(p, axis=1)]
                met = interval_metrics(part.outcome_class, p)
                interval_metric_rows.append({
                    "model_family": family,
                    "feature_variant": variant,
                    "split_name": split,
                    **{k: v for k, v in met.items() if k != "per_class"},
                    "details": met["per_class"],
                })
                for i, (_, row) in enumerate(part.iterrows()):
                    interval_prediction_rows.append({
                        "model_family": family,
                        "feature_variant": variant,
                        "person_period_id": int(row.person_period_id),
                        "source_training_example_id": int(row.source_training_example_id),
                        "person_id": int(row.person_id),
                        "split_name": split,
                        "interval_index": int(row.interval_index),
                        "y_true": row.outcome_class,
                        "y_pred": pred[i],
                        **{f"p_{c}": float(p[i, j]) for j, c in enumerate(CLASSES)},
                    })

                cutoff_part = cutoff_work[cutoff_work.split_name == split].copy()
                grid = expand_all_intervals(cutoff_part)
                gp = model_probs(model, grid, cols)
                horizon_frames.append(
                    compose_horizon_predictions(cutoff_part, grid, gp, family, variant)
                )

    interval_metrics_df = pd.DataFrame(interval_metric_rows)
    interval_preds_df = pd.DataFrame(interval_prediction_rows)
    horizons_df = pd.concat(horizon_frames, ignore_index=True)
    horizon_metrics_df = pd.DataFrame(horizon_metrics(horizons_df))

    interval_metrics_df.assign(
        details=interval_metrics_df.details.map(json.dumps)
    ).to_csv(out / "interval_metrics.csv", index=False)
    interval_preds_df.to_csv(out / "interval_predictions.csv.gz", index=False, compression="gzip")
    horizons_df.to_csv(out / "horizon_predictions.csv.gz", index=False, compression="gzip")
    horizon_metrics_df.assign(
        details=horizon_metrics_df.details.map(json.dumps)
    ).to_csv(out / "horizon_metrics.csv", index=False)
    (out / "model_manifest.json").write_text(
        json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Person-clustered paired uncertainty for the scientific feature comparisons.
    comparisons = {}
    test_pred = interval_preds_df[
        (interval_preds_df.split_name == "test")
        & (interval_preds_df.model_family.isin(["multinomial_logistic", "hist_gradient_boosting"]))
    ].copy()
    pairs = [
        ("history_plus_bazi_minus_history", "history_plus_bazi_v1", "history_reality_v1"),
        ("bazi_minus_raw_calendar", "bazi_objective_only_v1", "raw_birth_calendar_v1"),
        ("bazi_minus_placebo", "bazi_objective_only_v1", "bazi_decade_shuffle_placebo_v1"),
    ]
    for family in ["multinomial_logistic", "hist_gradient_boosting"]:
        comparisons[family] = {}
        fam = test_pred[test_pred.model_family == family]
        for key, akey, bkey in pairs:
            a = fam[fam.feature_variant == akey]
            b = fam[fam.feature_variant == bkey]
            comparisons[family][key] = bootstrap_pair(a, b)

    summary = {
        "round": "final-v1-round4",
        "protocol_key": PROTOCOL_KEY,
        "trajectory_dataset_id": TRAJECTORY_DATASET_ID,
        "trajectory_fingerprint": TRAJECTORY_FINGERPRINT,
        "source_dataset_id": SOURCE_DATASET_ID,
        "source_fingerprint": SOURCE_FINGERPRINT,
        "split_scenario": SCENARIO,
        "seed": SEED,
        "cutoff_rows": int(len(cutoffs)),
        "person_period_rows": int(len(data)),
        "people": int(cutoffs.person_id.nunique()),
        "split_period_rows": split_counts,
        "split_cutoff_rows": cutoff_split_counts,
        "outcome_counts": {k: int(v) for k, v in Counter(data.outcome_class).items()},
        "intervals_years": INTERVALS,
        "horizons_years": HORIZONS,
        "models": ["interval_prior", "multinomial_logistic", "hist_gradient_boosting"],
        "feature_variants": VARIANTS,
        "test_interval_metrics": interval_metrics_df[
            interval_metrics_df.split_name == "test"
        ][[
            "model_family", "feature_variant", "n", "accuracy", "balanced_accuracy",
            "macro_f1", "log_loss", "brier_multiclass", "ece_10bin",
            "event_vs_no_event_brier", "n_event",
            "conditional_domain_log_loss", "conditional_domain_macro_f1"
        ]].to_dict(orient="records"),
        "test_horizon_metrics": horizon_metrics_df[
            horizon_metrics_df.split_name == "test"
        ][[
            "model_family", "feature_variant", "horizon_years", "n", "log_loss",
            "brier_multiclass", "event_vs_no_event_brier", "macro_f1"
        ]].to_dict(orient="records"),
        "paired_person_bootstrap_test": comparisons,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "notes": [
            "No Round 4 hyperparameter selection occurred.",
            "Primary probability models use no class balancing.",
            "Partial censor intervals are absent from the frozen person-period likelihood.",
            "Risk set stops after the first observed target.",
            "Horizon predictions compose interval cause-specific probabilities into cumulative incidence.",
            "Horizon metrics exclude cutoff states censored before that horizon without a known later target.",
            "Paired bootstrap resamples people and reports negative deltas as favoring the first-named feature variant.",
        ],
    }
    (out / "round4_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    checksums = {}
    for p in sorted(out.rglob("*")):
        if p.is_file():
            checksums[str(p.relative_to(out))] = file_sha256(p)
    (out / "SHA256SUMS.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
