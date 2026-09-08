"""features/feature_engineering.py - Feature Pipeline v3.0

Builds the authoritative Joined Feature Table and its data dictionary/QA report.

Deliverables: exact 1/7/30 calendar-day lags; leakage-safe 7/30/90-day
mean/std/volatility; seasonality; disruption flags; date joins; QC; dictionary.

Use either:
  CLEANED_MASTER_PATH=/path/to/cleaned_merged_source.csv
or:
  FEATURE_SOURCES_JSON='{"voyages":"...","indices":"...","commodities":"...","disruptions":"..."}'
  FEATURE_BASE_SOURCE=voyages

Repository default: Data/Processed/cargocast_ml_dataset.csv -> features/joined_feature_table_v3.csv
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd

PIPELINE_VERSION = "3.0.0"
OUTPUT_DIR = Path(os.getenv("FEATURE_OUTPUT_DIR", "features"))
OUTPUT_FEATURE_PATH = OUTPUT_DIR / "joined_feature_table_v3.csv"
OUTPUT_DICTIONARY_PATH = OUTPUT_DIR / "joined_feature_table_v3_data_dictionary.csv"
OUTPUT_QA_PATH = OUTPUT_DIR / "joined_feature_table_v3_qa.csv"

LAGS_DAYS: Tuple[int, ...] = (1, 7, 30)
ROLLING_WINDOWS_DAYS: Tuple[int, ...] = (7, 30, 90)
OUTLIER_Z_THRESHOLD = float(os.getenv("FEATURE_OUTLIER_Z_THRESHOLD", "4.0"))

SERIES_TO_ENGINEER: Tuple[str, ...] = (
    "bdi", "bci", "bpi", "bsi", "bhsi", "iron_ore_price",
    "coking_coal_price", "usd_inr_rate", "bunker_vlsfo_price",
    "bunker_ifo380_price", "china_iron_ore_imports", "freight_rate_per_tonne",
)
CATEGORICAL_COLUMNS: Tuple[str, ...] = (
    "vessel_type", "cargo_type", "origin_port", "destination_port", "shock_type"
)
DISRUPTION_FLAG_COLUMNS: Tuple[str, ...] = (
    "disruption_flag", "weather_disruption_flag", "market_shock_flag",
    "port_disruption_flag", "cyclone_active",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger("feature_engineering")


def require_date(df: pd.DataFrame, name: str = "dataframe") -> pd.DataFrame:
    if "date" not in df.columns:
        raise ValueError(f"{name} must contain a 'date' column")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    bad = int(out["date"].isna().sum())
    if bad:
        raise ValueError(f"{name} contains {bad} invalid/missing date values")
    return out


def validate_unique_dates(df: pd.DataFrame, source_name: str) -> None:
    dup = int(df["date"].duplicated().sum())
    if dup:
        ex = (df.loc[df["date"].duplicated(keep=False), "date"]
                .dt.strftime("%Y-%m-%d").drop_duplicates().head(5).tolist())
        raise ValueError(f"{source_name}: {dup} duplicate date rows; examples={ex}")


def load_csv_sources(source_paths: Mapping[str, str | Path]) -> Dict[str, pd.DataFrame]:
    if not source_paths:
        raise ValueError("No source paths configured")
    sources = {}
    for name, path in source_paths.items():
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Source '{name}' not found: {p}")
        frame = require_date(pd.read_csv(p), name)
        validate_unique_dates(frame, name)
        sources[str(name)] = frame
        LOGGER.info("Loaded %-15s rows=%d cols=%d", name, len(frame), len(frame.columns))
    return sources


def join_sources(sources: Mapping[str, pd.DataFrame], base_source: str | None = None) -> pd.DataFrame:
    """Left-join date-level source tables; reject collisions and row multiplication."""
    if not sources:
        raise ValueError("No sources supplied")
    names = list(sources)
    base_source = base_source or ("voyages" if "voyages" in sources else names[0])
    if base_source not in sources:
        raise KeyError(f"Base source '{base_source}' not found")
    master = require_date(sources[base_source], base_source)
    validate_unique_dates(master, base_source)
    for name, frame in sources.items():
        if name == base_source:
            continue
        frame = require_date(frame, name)
        validate_unique_dates(frame, name)
        collisions = (set(master.columns) & set(frame.columns)) - {"date"}
        if collisions:
            raise ValueError(f"Column collisions joining {name}: {sorted(collisions)}")
        before = len(master)
        master = master.merge(frame, on="date", how="left", validate="one_to_one", sort=True)
        if len(master) != before:
            raise RuntimeError(f"Join with {name} changed row count {before}->{len(master)}")
    return master.sort_values("date").reset_index(drop=True)


def compute_lags_and_rollings(df: pd.DataFrame, target_cols: Sequence[str] = SERIES_TO_ENGINEER) -> pd.DataFrame:
    """Exact calendar lags plus rolling windows that exclude the current day."""
    out = require_date(df).sort_values("date").reset_index(drop=True)
    x = out.set_index("date")
    generated = {}
    for col in target_cols:
        if col not in x.columns:
            LOGGER.warning("Skipping missing series: %s", col)
            continue
        s = pd.to_numeric(x[col], errors="coerce")
        for lag in LAGS_DAYS:
            lookup = s.copy()
            lookup.index = lookup.index + pd.Timedelta(days=lag)
            lookup = lookup.groupby(level=0).last()
            generated[f"{col}_lag_{lag}"] = pd.Series(x.index.map(lookup), index=x.index)
        for window in ROLLING_WINDOWS_DAYS:
            roll = s.rolling(f"{window}D", min_periods=1, closed="left")
            mean = roll.mean()
            std = roll.std()
            generated[f"{col}_{window}d_avg"] = mean
            generated[f"{col}_{window}d_std"] = std
            generated[f"{col}_{window}d_vol"] = std / mean.abs().replace(0, np.nan)
    if generated:
        # Re-running the pipeline on an older feature table should replace, not duplicate,
        # legacy engineered columns.
        existing = [c for c in generated if c in x.columns]
        if existing:
            x = x.drop(columns=existing)
        x = pd.concat([x, pd.DataFrame(generated, index=x.index)], axis=1)
    return x.reset_index()


def engineer_seasonality_and_disruptions(df: pd.DataFrame) -> pd.DataFrame:
    out = require_date(df)
    out["month"] = out.date.dt.month
    out["day_of_week"] = out.date.dt.dayofweek
    out["quarter"] = out.date.dt.quarter
    out["week_of_year"] = out.date.dt.isocalendar().week.astype(int)
    out["day_of_year"] = out.date.dt.dayofyear

    # Project convention: South Asian monsoon = Jun-Sep.
    out["monsoon_flag"] = out.month.isin([6, 7, 8, 9]).astype(int)
    out["is_monsoon"] = out["monsoon_flag"]
    out["is_winter"] = out.month.isin([12, 1, 2]).astype(int)
    out["is_summer"] = out.month.isin([3, 4, 5]).astype(int)
    # Project convention: cyclone season = Apr-May and Oct-Dec.
    out["cyclone_season_flag"] = out.month.isin([4, 5, 10, 11, 12]).astype(int)

    pieces = []
    for col in DISRUPTION_FLAG_COLUMNS:
        if col in out.columns:
            pieces.append(pd.to_numeric(out[col], errors="coerce").fillna(0).gt(0))
    if "shock_type" in out.columns:
        s = out["shock_type"].astype("string").str.strip().str.lower()
        pieces.append(s.notna() & s.ne("") & s.ne("none"))
    if pieces:
        out["disruption_event_flag"] = pd.concat(pieces, axis=1).any(axis=1).astype(int)
    elif "disruption_event_flag" not in out.columns:
        out["disruption_event_flag"] = 0
    return out


def engineer_domain_voyage_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"distance_nm", "vessel_speed_knots"}.issubset(out.columns):
        d = pd.to_numeric(out["distance_nm"], errors="coerce")
        v = pd.to_numeric(out["vessel_speed_knots"], errors="coerce")
        out["voyage_days_calc"] = d / (v * 24).replace(0, np.nan)
    if {"bunker_vlsfo_price", "fuel_consumption_penalty_factor"}.issubset(out.columns):
        out["fuel_cost_proxy"] = (pd.to_numeric(out["bunker_vlsfo_price"], errors="coerce") *
                                   pd.to_numeric(out["fuel_consumption_penalty_factor"], errors="coerce"))
    if "vessel_age_years" in out.columns:
        age = pd.to_numeric(out["vessel_age_years"], errors="coerce")
        out["vessel_age_0-5yr"] = age.le(5).fillna(False).astype(int)
        out["vessel_age_5-10yr"] = (age.gt(5) & age.le(10)).fillna(False).astype(int)
        out["vessel_age_10-15yr"] = (age.gt(10) & age.le(15)).fillna(False).astype(int)
        out["vessel_age_15yr+"] = age.gt(15).fillna(False).astype(int)
    return out


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    present = [c for c in CATEGORICAL_COLUMNS if c in df.columns]
    return pd.get_dummies(df, columns=present, drop_first=False, dtype=int) if present else df


def run_data_quality_checks(df: pd.DataFrame, outlier_columns: Sequence[str] | None = None,
                            z_threshold: float = OUTLIER_Z_THRESHOLD):
    """Return (df_with_outlier_flags, qa_result)."""
    work = require_date(df)
    sorted_dates = work.date.sort_values()
    deltas = sorted_dates.diff().dt.days.dropna()
    gap_count = int((deltas > 1).sum())
    max_gap = int(deltas.max()) if len(deltas) else 0
    qa_rows = []

    for col in work.columns:
        n = int(work[col].isna().sum())
        qa_rows.append({"check_type": "missingness", "column": col, "value": n,
                        "rate": float(n / len(work)) if len(work) else 0, "status": "WARN" if n else "PASS"})

    dup = int(work.date.duplicated().sum())
    qa_rows += [
        {"check_type": "duplicate_date_rows", "column": "date", "value": dup, "rate": np.nan,
         "status": "FAIL" if dup else "PASS"},
        {"check_type": "non_monotonic_dates", "column": "date", "value": int(not work.date.is_monotonic_increasing),
         "rate": np.nan, "status": "WARN" if not work.date.is_monotonic_increasing else "PASS"},
        {"check_type": "date_gaps_gt_1_day", "column": "date", "value": gap_count, "rate": np.nan,
         "status": "WARN" if gap_count else "PASS"},
        {"check_type": "max_date_gap_days", "column": "date", "value": max_gap, "rate": np.nan,
         "status": "WARN" if max_gap > 1 else "PASS"},
    ]

    if outlier_columns is None:
        outlier_columns = [c for c in (*SERIES_TO_ENGINEER, "freight_rate_per_tonne")
                           if c in work.columns]
    for col in outlier_columns:
        s = pd.to_numeric(work[col], errors="coerce")
        std = s.std()
        count = 0 if pd.isna(std) or std == 0 else int((((s - s.mean()) / std).abs() > z_threshold).sum())
        z = (s - s.mean()) / std if pd.notna(std) and std != 0 else pd.Series(0.0, index=work.index)
        work[f"{col}_outlier_flag"] = z.abs().gt(z_threshold).astype(int)
        qa_rows.append({"check_type": "zscore_outliers", "column": col, "value": count,
                        "rate": float(count / len(work)) if len(work) else 0, "status": "WARN" if count else "PASS"})

    qa = pd.DataFrame(qa_rows)
    summary = {
        "pipeline_version": PIPELINE_VERSION, "row_count": int(len(work)),
        "column_count": int(len(work.columns)),
        "date_min": work.date.min().date().isoformat() if len(work) else None,
        "date_max": work.date.max().date().isoformat() if len(work) else None,
        "duplicate_date_rows": dup, "date_gaps_gt_1_day": gap_count, "max_date_gap_days": max_gap,
        "columns_with_missing": int(work.isna().any().sum()),
        "rows_with_any_missing": int(work.isna().any(axis=1).sum()),
        "qa_failures": int((qa.status == "FAIL").sum()),
    }
    return work, {"report": qa, "summary": summary}


def build_data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    base = {
        "date": ("Temporal metadata", "calendar date"),
        "bdi": ("Baltic Shipping Indices", "Baltic Dry Index"),
        "bci": ("Baltic Shipping Indices", "Baltic Capesize Index"),
        "bpi": ("Baltic Shipping Indices", "Baltic Panamax Index"),
        "bsi": ("Baltic Shipping Indices", "Baltic Supramax Index"),
        "bhsi": ("Baltic Shipping Indices", "Baltic Handysize Index"),
        "iron_ore_price": ("Commodity prices", "Iron ore benchmark price"),
        "coking_coal_price": ("Commodity prices", "Coking coal benchmark price"),
        "usd_inr_rate": ("FX", "USD/INR rate"),
        "bunker_vlsfo_price": ("Bunker prices", "VLSFO bunker price"),
        "bunker_ifo380_price": ("Bunker prices", "IFO380 bunker price"),
        "china_iron_ore_imports": ("Macro / trade", "China iron ore imports"),
        "freight_rate_per_tonne": ("Freight dataset", "Freight rate target"),
    }
    rows = []
    for col in df.columns:
        if col in base:
            src, meaning = base[col]
        elif "_lag_" in col:
            b, n = col.rsplit("_lag_", 1); src, meaning = "Feature Engineer v3", f"{n}-calendar-day lag of {b}"
        elif any(col.endswith(f"_{w}d_{m}") for w in (7,30,90) for m in ("avg","std","vol")):
            parts = col.rsplit("_", 2); b, w, m = parts; src, meaning = "Feature Engineer v3", f"{w} trailing {m} of {b}; current day excluded"
        elif col.endswith("_outlier_flag"):
            src, meaning = "Feature Engineer v3 QC", f"1 when {col[:-14]} has |z-score| > {OUTLIER_Z_THRESHOLD}"
        elif col in {"month","day_of_week","quarter","week_of_year","day_of_year"}:
            src, meaning = "Temporal metadata", f"Calendar {col} extracted from date"
        elif col in {"monsoon_flag","is_monsoon"}:
            src, meaning = "Feature Engineer v3", "1 for June through September"
        elif col == "cyclone_season_flag":
            src, meaning = "Feature Engineer v3", "1 for April-May and October-December"
        elif col in DISRUPTION_FLAG_COLUMNS or col == "disruption_event_flag":
            src, meaning = "Data Lead disruption dataset", "Disruption/event indicator"
        elif col.startswith(("vessel_age_", "vessel_type_", "cargo_type_", "origin_port_", "destination_port_", "shock_type_")):
            src, meaning = "Feature Engineer v3", "Derived or one-hot encoded categorical feature"
        elif col in {"voyage_days_calc","fuel_cost_proxy"}:
            src, meaning = "Feature Engineer v3", "Derived voyage economics feature"
        else:
            src, meaning = "Joined upstream source", "Upstream field preserved in master feature table"
        rows.append({"column": col, "meaning": meaning, "source": src, "pipeline_version": PIPELINE_VERSION,
                     "dtype": str(df[col].dtype), "unit": ""})
    return pd.DataFrame(rows).sort_values("column").reset_index(drop=True)


def build_feature_table(master_df: pd.DataFrame):
    df = compute_lags_and_rollings(master_df)
    df = engineer_seasonality_and_disruptions(df)
    df = engineer_domain_voyage_features(df)
    df = encode_categoricals(df)
    df, qa = run_data_quality_checks(df)
    df = df.sort_values("date").reset_index(drop=True)
    return df, build_data_dictionary(df), qa


def configured_sources() -> Dict[str, str]:
    raw = os.getenv("FEATURE_SOURCES_JSON", "").strip()
    if not raw:
        return {}
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not obj:
        raise ValueError("FEATURE_SOURCES_JSON must be a non-empty JSON object")
    return {str(k): str(v) for k, v in obj.items()}


def load_input() -> pd.DataFrame:
    src = configured_sources()
    if src:
        base = os.getenv("FEATURE_BASE_SOURCE") or ("voyages" if "voyages" in src else next(iter(src)))
        return join_sources(load_csv_sources(src), base_source=base)
    path = Path(os.getenv("CLEANED_MASTER_PATH", "Data/Processed/cargocast_ml_dataset.csv"))
    if not path.exists():
        raise FileNotFoundError(
            "No input found. Set CLEANED_MASTER_PATH or FEATURE_SOURCES_JSON before running the pipeline."
        )
    return require_date(pd.read_csv(path), "cleaned master")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Feature Engineering Pipeline v%s", PIPELINE_VERSION)
    master = load_input()
    table, dictionary, qa = build_feature_table(master)
    table.to_csv(OUTPUT_FEATURE_PATH, index=False)
    dictionary.to_csv(OUTPUT_DICTIONARY_PATH, index=False)
    qa["report"].to_csv(OUTPUT_QA_PATH, index=False)
    LOGGER.info("Master=%s shape=%s", OUTPUT_FEATURE_PATH, table.shape)
    LOGGER.info("Dictionary=%s rows=%d", OUTPUT_DICTIONARY_PATH, len(dictionary))
    LOGGER.info("QA=%s summary=%s", OUTPUT_QA_PATH, json.dumps(qa["summary"]))
    if qa["summary"]["qa_failures"]:
        raise RuntimeError(f"QA failures detected; inspect {OUTPUT_QA_PATH}")


if __name__ == "__main__":
    main()
