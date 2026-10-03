"""Experiment contract, not a trained weight file.
Expected input: a leakage-safe person-level table with `target_*` labels and pre-cutoff features.
"""
from dataclasses import dataclass
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

@dataclass
class Result:
    accuracy: float
    macro_f1: float
    log_loss: float

def train_eval(df: pd.DataFrame, target: str, numeric, categorical, train_until: int, test_from: int):
    train = df[df.birth_year <= train_until].copy()
    test = df[df.birth_year >= test_from].copy()
    pre = ColumnTransformer([
        ("num", Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler())]), numeric),
        ("cat", Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    pipe = Pipeline([("prep",pre),("model",LogisticRegression(max_iter=2000,class_weight="balanced"))])
    pipe.fit(train[numeric+categorical], train[target])
    pred = pipe.predict(test[numeric+categorical])
    proba = pipe.predict_proba(test[numeric+categorical])
    return pipe, Result(accuracy_score(test[target],pred), f1_score(test[target],pred,average="macro"), log_loss(test[target],proba))
