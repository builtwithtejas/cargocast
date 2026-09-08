"""CargoCast quantile regression / uncertainty module.

This replaces the notebook's residual +/- 1.96*std approximation with actual
quantile regression models at the 10th, 50th and 90th percentiles.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .forecasting import (
    DATA_DIR,
    FEATURE_TABLE,
    FREIGHT_TARGET,
    _load_feature_table,
    _split_master,
    _numeric_features,
)

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
QUANTILE_PATH = ARTIFACT_DIR / "freight_quantile_models.joblib"
META_PATH = ARTIFACT_DIR / "quantile_metadata.json"
QUANTILES = (0.10, 0.50, 0.90)


def _make_quantile_pipeline(alpha: float) -> Pipeline:
    model = GradientBoostingRegressor(
        loss="quantile",
        alpha=alpha,
        n_estimators=150,
        learning_rate=0.03,
        max_depth=3,
        min_samples_leaf=5,
        random_state=42,
    )
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", model),
    ])


def train_quantile_models(feature_table_path: Path = FEATURE_TABLE) -> dict:
    master = _load_feature_table(Path(feature_table_path))
    splits = _split_master(master)
    train = splits["train"]
    val = splits["validation"]
    test = splits["test"]
    features = _numeric_features(train, FREIGHT_TARGET)

    # Tune/evaluate conceptually on validation using train only, then refit on train+validation.
    validation_metrics = {}
    train_only_models = {}
    for q in QUANTILES:
        pipe = _make_quantile_pipeline(q)
        pipe.fit(train[features], pd.to_numeric(train[FREIGHT_TARGET], errors="coerce"))
        train_only_models[q] = pipe
        pred = pipe.predict(val[features])
        y = pd.to_numeric(val[FREIGHT_TARGET], errors="coerce").to_numpy()
        validation_metrics[str(q)] = {"mae": float(np.mean(np.abs(y - pred))), "n": int(len(y))}

    trainval = pd.concat([train, val], axis=0).sort_values("date")
    models = {}
    for q in QUANTILES:
        pipe = _make_quantile_pipeline(q)
        pipe.fit(trainval[features], pd.to_numeric(trainval[FREIGHT_TARGET], errors="coerce"))
        models[q] = pipe

    bundle = {"models": models, "features": features, "quantiles": QUANTILES, "target": FREIGHT_TARGET}
    joblib.dump(bundle, QUANTILE_PATH)

    test = splits["test"]
    metrics = {}
    for q, pipe in models.items():
        pred = pipe.predict(test[features])
        y = pd.to_numeric(test[FREIGHT_TARGET], errors="coerce").to_numpy()
        error = y - pred
        metrics[str(q)] = {"mae": float(np.mean(np.abs(error))), "n": int(len(y))}

    meta = {"quantiles": QUANTILES, "feature_count": len(features), "validation_metrics": validation_metrics, "test_metrics": metrics, "artifact": str(QUANTILE_PATH.relative_to(ROOT))}
    META_PATH.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    LOGGER.info("Saved quantile model bundle: %s", QUANTILE_PATH)
    return meta


def _load_bundle() -> dict:
    if not QUANTILE_PATH.exists():
        train_quantile_models()
    return joblib.load(QUANTILE_PATH)


def add_uncertainty_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Add lower/upper bounds using fitted quantile models.

    `forecast_freight_rate` supplies the underlying model-feature columns with
    `_feature_` prefixes; this function consumes them and strips them before return.
    """
    out = df.copy()
    if "date" not in out.columns or "forecast" not in out.columns:
        raise ValueError("Input must contain date and forecast columns")
    bundle = _load_bundle()
    features = bundle["features"]
    feature_frame = pd.DataFrame({f: out.get(f"_feature_{f}", np.nan) for f in features})
    lower = bundle["models"][0.10].predict(feature_frame)
    upper = bundle["models"][0.90].predict(feature_frame)
    # Enforce a valid interval even for pathological extrapolation.
    lower = np.minimum(lower, upper)
    upper = np.maximum(lower, upper)
    out["lower"] = lower
    out["upper"] = upper
    return out[["date", "forecast", "lower", "upper"]]


if __name__ == "__main__":
    print(json.dumps(train_quantile_models(), indent=2))
