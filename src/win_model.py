"""
Win probability model: given what we know about a deal when it is created, how likely is it to
be won?

Rules I hold myself to here:
  * Only features known at creation time. Close date, stage, lost reason, cycle length and
    anything else that is only known once the deal moves are left out, or the model "predicts"
    the past.
  * Time-based split. The model is trained on deals that had already closed before a cutoff date
    and tested on deals created after it, as if I had built it on that date. A random split would
    let 2026 deals teach the model about 2025.
  * A simple baseline first (logistic regression), then see if gradient boosting earns its place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CUTOFF = date(2025, 10, 1)
SEED = 7

CATEGORICAL = ["channel", "deal_type", "product", "size_segment", "sector", "region", "partner_type"]
NUMERIC = ["log_amount", "log_employees"]
FEATURES = CATEGORICAL + NUMERIC
# Known only after the deal moves or closes: never a feature
LEAKY = {"close_date", "stage", "is_won", "is_closed", "lost_reason", "last_open_stage", "cycle_days"}


def add_features(deals: pd.DataFrame) -> pd.DataFrame:
    df = deals.copy()
    df["created_date"] = pd.to_datetime(df["created_date"])
    df["close_date"] = pd.to_datetime(df["close_date"])
    df["log_amount"] = np.log(df["amount"])
    df["log_employees"] = np.log(df["employees"])
    return df


def time_split(df: pd.DataFrame, cutoff: date = CUTOFF) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train: deals already closed before the cutoff. Test: deals created on or after it, closed by now."""
    cutoff = pd.Timestamp(cutoff)
    closed = df[df["is_closed"]]
    train = closed[closed["close_date"] < cutoff]
    test = closed[closed["created_date"] >= cutoff]
    return train, test


def make_models() -> dict[str, Pipeline]:
    def prep():
        return ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ])
    return {
        "Logistic regression": Pipeline([
            ("prep", prep()),
            ("model", LogisticRegression(C=0.5, max_iter=2000)),
        ]),
        "Gradient boosting": Pipeline([
            ("prep", prep()),
            ("model", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                                     min_samples_leaf=40, random_state=SEED)),
        ]),
    }


@dataclass
class ModelReport:
    metrics: pd.DataFrame
    calibration: pd.DataFrame
    importance: pd.DataFrame
    coefficients: pd.DataFrame
    test_predictions: pd.DataFrame
    open_scored: pd.DataFrame
    train_rows: int
    test_rows: int


def calibration_table(y: pd.Series, p: np.ndarray, bins: int = 8) -> pd.DataFrame:
    """Mean predicted vs observed win rate in equal-sized bins of predicted probability."""
    frame = pd.DataFrame({"y": y.to_numpy(), "p": p})
    frame["bin"] = pd.qcut(frame["p"], q=bins, labels=False, duplicates="drop")
    return (frame.groupby("bin")
            .agg(mean_predicted=("p", "mean"), observed_win_rate=("y", "mean"), deals=("y", "size"))
            .reset_index(drop=True))


def run(deals: pd.DataFrame, open_pipeline: pd.DataFrame | None = None) -> ModelReport:
    assert not LEAKY & set(FEATURES)
    df = add_features(deals)
    train, test = time_split(df)
    y_train, y_test = train["is_won"].astype(int), test["is_won"].astype(int)

    # A model that knows nothing but the historical win rate: the bar to beat on Brier score
    base_rate = y_train.mean()
    rows = [{"model": "Base rate only", "roc_auc": 0.5,
             "brier": brier_score_loss(y_test, np.full(len(y_test), base_rate)),
             "log_loss": log_loss(y_test, np.full(len(y_test), base_rate))}]

    models, preds, calib = make_models(), {}, []
    for name, pipe in models.items():
        pipe.fit(train[FEATURES], y_train)
        p = pipe.predict_proba(test[FEATURES])[:, 1]
        preds[name] = p
        rows.append({"model": name, "roc_auc": roc_auc_score(y_test, p),
                     "brier": brier_score_loss(y_test, p), "log_loss": log_loss(y_test, p)})
        calib.append(calibration_table(y_test, p).assign(model=name))
    metrics = pd.DataFrame(rows).round(4)

    lr = models["Logistic regression"]
    imp = permutation_importance(lr, test[FEATURES], y_test, scoring="roc_auc",
                                 n_repeats=20, random_state=SEED)
    importance = (pd.DataFrame({"feature": FEATURES, "auc_drop_mean": imp.importances_mean,
                                "auc_drop_std": imp.importances_std})
                  .sort_values("auc_drop_mean", ascending=False).round(4))

    names = lr.named_steps["prep"].get_feature_names_out()
    coefs = lr.named_steps["model"].coef_[0]
    coefficients = (pd.DataFrame({"feature": [n.split("__", 1)[1] for n in names],
                                  "coefficient": coefs, "odds_ratio": np.exp(coefs)})
                    .sort_values("coefficient", ascending=False).round(3))

    test_predictions = test[["deal_id", "created_date", "is_won"]].assign(
        **{f"p_{k.split()[0].lower()}": v for k, v in preds.items()})

    # Score the open pipeline with the baseline refitted on every closed deal we have
    open_scored = pd.DataFrame()
    if open_pipeline is not None:
        closed = df[df["is_closed"]]
        final = make_models()["Logistic regression"].fit(closed[FEATURES], closed["is_won"].astype(int))
        current = df[~df["is_closed"]].merge(
            open_pipeline[["deal_id", "p_win_from_stage", "weighted_amount", "is_stuck", "days_in_stage"]],
            on="deal_id")
        current["p_win_model"] = final.predict_proba(current[FEATURES])[:, 1].round(3)
        open_scored = (current[["deal_id", "deal_name", "channel", "deal_type", "size_segment", "stage",
                                "amount", "p_win_model", "p_win_from_stage", "weighted_amount",
                                "days_in_stage", "is_stuck"]]
                       .sort_values("p_win_model", ascending=False).reset_index(drop=True))

    return ModelReport(metrics, pd.concat(calib, ignore_index=True), importance, coefficients,
                       test_predictions, open_scored, len(train), len(test))
