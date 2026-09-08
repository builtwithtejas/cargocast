"""CargoCast forecasting module.

Productionized from the ML Engineer #1 forecasting notebook.

Public API used by backend/pipeline.py:
    forecast_freight_rate(route, horizon_days)

Additional API:
    forecast_demand(horizon_days)
    train_models(...)
    evaluate_freight_model(...)

The notebook's XGBoost settings are preserved. The project split files are
used by date for train/validation/test evaluation. Model artifacts are saved
under models/artifacts/ so deployment does not retrain on every startup.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

ROOT = Path(__file__).resolve().parents[1]
FEATURE_TABLE = ROOT / "features" / "joined_feature_table_v3.csv"
DATA_DIR = ROOT / "Data" / "Processed"
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

FREIGHT_MODEL_PATH = ARTIFACT_DIR / "freight_xgb.joblib"
DEMAND_MODEL_PATH = ARTIFACT_DIR / "demand_xgb.joblib"
META_PATH = ARTIFACT_DIR / "forecasting_metadata.json"

FREIGHT_TARGET = "freight_rate_per_tonne"
DEMAND_TARGET = "cargo_tonnage"
EXCLUDED_FEATURES = {
    "date",
    FREIGHT_TARGET,
    f"{FREIGHT_TARGET}_outlier_flag",
    DEMAND_TARGET,
}

XGB_PARAMS = {
    "objective": "reg:squarederror",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
}


def _load_feature_table(path: Path = FEATURE_TABLE) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Feature table not found: {path}")
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("Feature table must contain 'date'")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise ValueError("Feature table contains invalid dates")
    return df.sort_values("date").reset_index(drop=True)


def _load_split_dates(name: str) -> pd.DatetimeIndex:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Split file not found: {path}")
    split = pd.read_csv(path, usecols=["date"])
    dates = pd.to_datetime(split["date"], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{path} contains invalid dates")
    return pd.DatetimeIndex(dates).unique().sort_values()


def _split_master(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    masks = {}
    for name in ("train", "validation", "test"):
        dates = _load_split_dates(name)
        masks[name] = df["date"].isin(dates)
    mask_items = list(masks.values())
    overlap = sum(int((mask_items[i] & mask_items[j]).sum()) for i in range(len(mask_items)) for j in range(i + 1, len(mask_items)) )
    if overlap:
        raise ValueError("Train/validation/test dates overlap")
    return {name: df.loc[mask].copy() for name, mask in masks.items()}


def _numeric_features(df: pd.DataFrame, target: str) -> list[str]:
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    features = [c for c in numeric if c not in EXCLUDED_FEATURES and c != target]
    if not features:
        raise ValueError("No numeric model features available")
    return features


def _make_pipeline() -> Pipeline:
    model = XGBRegressor(**XGB_PARAMS)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", model),
    ])


def _fit_target(df: pd.DataFrame, target: str) -> Tuple[Pipeline, list[str]]:
    features = _numeric_features(df, target)
    pipeline = _make_pipeline()
    pipeline.fit(df[features], pd.to_numeric(df[target], errors="coerce"))
    return pipeline, features


def train_models(feature_table_path: Path = FEATURE_TABLE) -> dict:
    """Train freight and demand XGBoost models; evaluate on untouched test set."""
    master = _load_feature_table(Path(feature_table_path))
    splits = _split_master(master)
    results: dict = {"pipeline": "CargoCast Forecasting", "model": "XGBoost", "xgb_params": XGB_PARAMS.copy()}

    # Model selection/evaluation uses train and validation; final production model is fit on train+validation.
    for target, artifact_path, label in [
        (FREIGHT_TARGET, FREIGHT_MODEL_PATH, "freight"),
        (DEMAND_TARGET, DEMAND_MODEL_PATH, "demand"),
    ]:
        train = splits["train"]
        val = splits["validation"]
        test = splits["test"]

        # Genuine validation estimate: fit only on train.
        validation_model, features = _fit_target(train, target)
        metrics = {}
        y_val = pd.to_numeric(val[target], errors="coerce")
        val_pred = validation_model.predict(val[features])
        metrics["validation"] = {
            "r2": float(r2_score(y_val, val_pred)),
            "mae": float(mean_absolute_error(y_val, val_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_val, val_pred))),
            "n": int(len(val)),
        }

        # Final production model is fit on train+validation; test remains untouched.
        trainval = pd.concat([train, val], axis=0).sort_values("date")
        pipeline, final_features = _fit_target(trainval, target)
        if final_features != features:
            raise RuntimeError("Feature columns changed between train and train+validation")
        y_true = pd.to_numeric(test[target], errors="coerce")
        y_pred = pipeline.predict(test[features])
        metrics["test"] = {
            "r2": float(r2_score(y_true, y_pred)),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "n": int(len(test)),
        }
        bundle = {"pipeline": pipeline, "features": features, "target": target, "model_version": "xgb_notebook_params_v1"}
        joblib.dump(bundle, artifact_path)
        results[label] = {"artifact": str(artifact_path.relative_to(ROOT)), "feature_count": len(features), "metrics": metrics}
        LOGGER.info("Saved %s model: %s", label, artifact_path)

    META_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


def _load_bundle(path: Path) -> dict:
    if not path.exists():
        LOGGER.warning("Model artifact missing: %s. Training models now.", path)
        train_models()
    return joblib.load(path)


def _base_future_row(master: pd.DataFrame, date: pd.Timestamp) -> dict:
    latest = master.iloc[-1].to_dict()
    latest["date"] = date
    calendar_values = {
        "month": date.month,
        "day_of_week": date.dayofweek,
        "quarter": date.quarter,
        "week_of_year": int(date.isocalendar().week),
        "day_of_year": date.dayofyear,
        "monsoon_flag": int(date.month in (6, 7, 8, 9)),
        "is_monsoon": int(date.month in (6, 7, 8, 9)),
        "is_winter": int(date.month in (12, 1, 2)),
        "is_summer": int(date.month in (3, 4, 5)),
        "cyclone_season_flag": int(date.month in (4, 5, 10, 11, 12)),
    }
    for key, value in calendar_values.items():
        if key in latest:
            latest[key] = value
    return latest


def _set_target_history_features(row: dict, series: pd.Series, date: pd.Timestamp, target: str) -> None:
    if target not in row:
        return
    for lag in (1, 7, 30):
        col = f"{target}_lag_{lag}"
        if col in row:
            row[col] = series.get(date - pd.Timedelta(days=lag), np.nan)
    window = series.loc[(series.index >= date - pd.Timedelta(days=90)) & (series.index < date)]
    for days in (7, 30, 90):
        col_base = f"{target}_{days}d"
        subset = window.loc[window.index >= date - pd.Timedelta(days=days)].dropna()
        if subset.empty:
            vals = (np.nan, np.nan, np.nan)
        else:
            mean = float(subset.mean())
            std = float(subset.std()) if len(subset) > 1 else 0.0
            vol = std / abs(mean) if mean else np.nan
            vals = (mean, std, vol)
        for suffix, value in zip(("avg", "std", "vol"), vals):
            col = f"{col_base}_{suffix}"
            if col in row:
                row[col] = value


def _predict_recursive(target: str, horizon_days: int, bundle: dict) -> pd.DataFrame:
    master = _load_feature_table()
    features = bundle["features"]
    pipeline = bundle["pipeline"]
    last_date = master["date"].max()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")

    # Known history plus recursive predictions for the target being forecast.
    history = pd.Series(
        pd.to_numeric(master[target], errors="coerce").to_numpy(),
        index=master["date"],
        dtype="float64",
    ).dropna()
    rows = []
    predictions = []
    for date in future_dates:
        row = _base_future_row(master, date)
        if target == FREIGHT_TARGET:
            _set_target_history_features(row, history, date, target)
        for f in features:
            if f not in row:
                row[f] = np.nan
        feature_frame = pd.DataFrame([{f: row[f] for f in features}])
        pred = float(pipeline.predict(feature_frame)[0])
        row["forecast"] = pred
        history.loc[date] = pred
        predictions.append(pred)
        rows.append(row)

    out = pd.DataFrame(rows)
    return pd.DataFrame({
        "date": future_dates,
        "forecast": predictions,
        **{f"_feature_{c}": out[c] for c in features if c in out.columns},
    })

def forecast_freight_rate(route: str, horizon_days: int = 30) -> pd.DataFrame:
    """Return forecast curve for backend integration. Route is accepted for API compatibility."""
    if horizon_days < 1 or horizon_days > 180:
        raise ValueError("horizon_days must be between 1 and 180")
    bundle = _load_bundle(FREIGHT_MODEL_PATH)
    LOGGER.info("Generating %d-day freight forecast for route=%s", horizon_days, route)
    return _predict_recursive(FREIGHT_TARGET, horizon_days, bundle)


def forecast_demand(horizon_days: int = 30) -> pd.DataFrame:
    if horizon_days < 1 or horizon_days > 180:
        raise ValueError("horizon_days must be between 1 and 180")
    bundle = _load_bundle(DEMAND_MODEL_PATH)
    out = _predict_recursive(DEMAND_TARGET, horizon_days, bundle)
    return out[["date", "forecast"]].rename(columns={"forecast": "demand_forecast"})


def evaluate_freight_model() -> dict:
    """Load metadata generated during training/evaluation."""
    if not META_PATH.exists():
        train_models()
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    return meta.get("freight", {})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(train_models(), indent=2))
