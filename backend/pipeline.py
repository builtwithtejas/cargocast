"""
backend/pipeline.py

Integration backbone for the Chartering Decision Support hackathon project.

This module is the ONLY thing the dashboard should import from. It exposes
four stable functions:

    get_forecast(route, horizon_days)      -> DataFrame[date, forecast, lower, upper]
    get_recommendation(route, horizon_days) -> dict (decision + reasoning)
    run_scenario(route, horizon_days, scenario_overrides) -> dict (updated recommendation)
    estimate_savings(route, lookback_days) -> dict (₹ savings vs naive baseline)

DESIGN PRINCIPLE: every teammate's module is imported behind a try/except.
If a teammate's real module isn't ready yet, we fall back to a mock with the
EXACT same function signature and return shape. This means:
  - the dashboard dev can build against this file from hour 1
  - as each real module lands, you delete nothing — just remove the fallback
  - nobody's late module blocks the demo

DATA CONTRACT (share this with the team, don't let it drift):

  Forecast DataFrame columns: ["date", "forecast", "lower", "upper"]
    - date: pd.Timestamp
    - forecast/lower/upper: float, freight rate in $/day or $/tonne (pick one, document it)

  Recommendation dict:
    {
        "route": str,
        "as_of_date": str (ISO date),
        "charter_decision": "SPOT" | "TIME_CHARTER",
        "timing_decision": "BUY_NOW" | "WAIT",
        "disruption_score": float (0-1, higher = more disruption risk),
        "confidence": float (0-1),
        "reasoning": str (plain language, shown directly in the dashboard),
    }

  Scenario result dict: same shape as Recommendation dict, plus:
    {
        ...,
        "scenario_applied": dict (echo of the overrides that were used),
        "baseline_recommendation": dict (what it would've been without the scenario),
    }

  Savings dict:
    {
        "route": str,
        "lookback_days": int,
        "naive_cost": float,
        "optimized_cost": float,
        "savings_amount": float,
        "savings_pct": float,
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline")


# --------------------------------------------------------------------------
# 1. IMPORT REAL MODULES WHERE AVAILABLE, ELSE FALL BACK TO MOCKS
# --------------------------------------------------------------------------

# --- ML Engineer #1: forecasting.py + quantile_regression.py ---
try:
    from models.forecasting import forecast_freight_rate  # type: ignore
    from models.quantile_regression import add_uncertainty_bands  # type: ignore

    _HAVE_REAL_FORECAST = True
    logger.info("Using REAL forecasting module.")
except ImportError:
    _HAVE_REAL_FORECAST = False
    logger.warning("forecasting module not found — using MOCK forecast generator.")

# --- ML Engineer #2: disruption scoring + decision engine ---
try:
    from nlp.disruption_scoring import get_disruption_score  # type: ignore

    _HAVE_REAL_NLP = True
    logger.info("Using REAL disruption scoring module.")
except ImportError:
    _HAVE_REAL_NLP = False
    logger.warning("disruption_scoring module not found — using MOCK disruption score.")

try:
    from decision_engine.charter_selector import select_charter_type  # type: ignore
    from decision_engine.timing_recommender import recommend_timing  # type: ignore
    from decision_engine.scenario_simulator import apply_scenario  # type: ignore

    _HAVE_REAL_DECISION = True
    logger.info("Using REAL decision engine module.")
except ImportError:
    _HAVE_REAL_DECISION = False
    logger.warning("decision_engine modules not found — using MOCK decision logic.")


# --------------------------------------------------------------------------
# 2. MOCK IMPLEMENTATIONS (same signatures as the real modules will have)
# --------------------------------------------------------------------------

def _mock_forecast_freight_rate(route: str, horizon_days: int) -> pd.DataFrame:
    """Deterministic-ish fake freight rate series with trend + seasonality + noise."""
    rng = np.random.default_rng(abs(hash(route)) % (2**32))
    base_rate = 18000.0  # $/day, e.g. Capesize-ish
    dates = pd.date_range(start=datetime.today().date(), periods=horizon_days, freq="D")
    trend = np.linspace(0, base_rate * 0.05, horizon_days)
    seasonal = base_rate * 0.03 * np.sin(np.linspace(0, 3 * np.pi, horizon_days))
    noise = rng.normal(0, base_rate * 0.01, horizon_days)
    forecast = base_rate + trend + seasonal + noise
    return pd.DataFrame({"date": dates, "forecast": forecast})


def _mock_add_uncertainty_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Widening confidence band the further out the forecast goes."""
    df = df.copy()
    horizon = np.arange(len(df))
    spread = df["forecast"].iloc[0] * (0.03 + 0.004 * horizon)
    df["lower"] = df["forecast"] - spread
    df["upper"] = df["forecast"] + spread
    return df[["date", "forecast", "lower", "upper"]]


def _mock_get_disruption_score(route: str, as_of_date: Optional[str] = None) -> float:
    """Fake disruption score 0-1. Swap for real VADER-based scorer."""
    rng = np.random.default_rng(abs(hash((route, as_of_date))) % (2**32))
    return float(np.clip(rng.beta(2, 6), 0, 1))


def _mock_select_charter_type(forecast_df: pd.DataFrame, disruption_score: float) -> tuple[str, str]:
    """Returns (decision, reasoning)."""
    near_term = forecast_df["forecast"].iloc[: min(7, len(forecast_df))].mean()
    later = forecast_df["forecast"].iloc[-min(7, len(forecast_df)):].mean()
    trending_up = later > near_term * 1.02
    volatile = disruption_score > 0.5

    if trending_up and not volatile:
        return "TIME_CHARTER", (
            f"Rates are trending up (near-term avg ${near_term:,.0f} -> "
            f"later avg ${later:,.0f}) with low disruption risk "
            f"({disruption_score:.2f}). Locking in a time charter now avoids "
            f"paying higher spot rates later."
        )
    return "SPOT", (
        f"Rates are {'volatile' if volatile else 'flat/falling'} "
        f"(disruption score {disruption_score:.2f}). Staying on spot keeps "
        f"flexibility until the picture is clearer."
    )


def _mock_recommend_timing(forecast_df: pd.DataFrame, disruption_score: float) -> tuple[str, str]:
    near_term = forecast_df["forecast"].iloc[: min(7, len(forecast_df))].mean()
    later = forecast_df["forecast"].iloc[-min(7, len(forecast_df)):].mean()
    if later > near_term * 1.03 and disruption_score < 0.6:
        return "BUY_NOW", "Forecast rates rise faster than disruption risk justifies waiting."
    return "WAIT", "Forecast is flat or disruption risk is high enough to justify waiting for more signal."


def _mock_apply_scenario(forecast_df: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    """Applies simple multiplicative/additive shocks to the forecast."""
    df = forecast_df.copy()
    fuel_pct = overrides.get("fuel_price_pct_change", 0.0)
    delay_days = overrides.get("delay_days", 0)
    demand_shock_pct = overrides.get("demand_shock_pct", 0.0)

    # crude but transparent: fuel and demand shocks shift the whole curve;
    # delay days shift the disruption-sensitive back half of the curve up.
    df["forecast"] = df["forecast"] * (1 + fuel_pct / 100 * 0.4 + demand_shock_pct / 100)
    if delay_days > 0:
        tail_idx = df.index[-max(1, len(df) // 2):]
        df.loc[tail_idx, "forecast"] *= 1 + min(delay_days, 30) * 0.01
    df["lower"] = df["forecast"] - (df.get("upper", df["forecast"]) - df.get("lower", df["forecast"])).abs() / 2
    df["upper"] = df["forecast"] + (df.get("upper", df["forecast"]) - df.get("lower", df["forecast"])).abs() / 2
    return df


# --------------------------------------------------------------------------
# 3. THIN WRAPPERS — pick real fn if available, else mock. Nothing else in
#    this file should ever call the imports/mocks directly except these.
# --------------------------------------------------------------------------

def _forecast_freight_rate(route: str, horizon_days: int) -> pd.DataFrame:
    if _HAVE_REAL_FORECAST:
        return forecast_freight_rate(route, horizon_days)  # noqa: F821
    return _mock_forecast_freight_rate(route, horizon_days)


def _add_uncertainty_bands(df: pd.DataFrame) -> pd.DataFrame:
    if _HAVE_REAL_FORECAST:
        return add_uncertainty_bands(df)  # noqa: F821
    return _mock_add_uncertainty_bands(df)


def _get_disruption_score(route: str, as_of_date: Optional[str] = None) -> float:
    if _HAVE_REAL_NLP:
        return get_disruption_score(route, as_of_date)  # noqa: F821
    return _mock_get_disruption_score(route, as_of_date)


def _select_charter_type(forecast_df: pd.DataFrame, disruption_score: float):
    if _HAVE_REAL_DECISION:
        return select_charter_type(forecast_df, disruption_score)  # noqa: F821
    return _mock_select_charter_type(forecast_df, disruption_score)


def _recommend_timing(forecast_df: pd.DataFrame, disruption_score: float):
    if _HAVE_REAL_DECISION:
        return recommend_timing(forecast_df, disruption_score)  # noqa: F821
    return _mock_recommend_timing(forecast_df, disruption_score)


def _apply_scenario(forecast_df: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    if _HAVE_REAL_DECISION:
        return apply_scenario(forecast_df, overrides)  # noqa: F821
    return _mock_apply_scenario(forecast_df, overrides)


# --------------------------------------------------------------------------
# 4. PUBLIC API — this is what dashboard/app.py imports
# --------------------------------------------------------------------------

def get_forecast(route: str, horizon_days: int = 30) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: date, forecast, lower, upper.
    This is the single source of truth the dashboard's chart is built from.
    """
    df = _forecast_freight_rate(route, horizon_days)
    df = _add_uncertainty_bands(df)
    return df


def get_recommendation(route: str, horizon_days: int = 30) -> dict:
    """
    Returns the charter + timing recommendation with plain-language reasoning.
    """
    forecast_df = get_forecast(route, horizon_days)
    disruption_score = _get_disruption_score(route)

    charter_decision, charter_reason = _select_charter_type(forecast_df, disruption_score)
    timing_decision, timing_reason = _recommend_timing(forecast_df, disruption_score)

    # crude confidence proxy: tighter bands -> higher confidence
    band_width = (forecast_df["upper"] - forecast_df["lower"]).mean()
    confidence = float(np.clip(1 - band_width / forecast_df["forecast"].mean(), 0, 1))

    return {
        "route": route,
        "as_of_date": datetime.today().date().isoformat(),
        "charter_decision": charter_decision,
        "timing_decision": timing_decision,
        "disruption_score": round(disruption_score, 3),
        "confidence": round(confidence, 3),
        "reasoning": f"{charter_reason} {timing_reason}",
    }


def run_scenario(route: str, horizon_days: int, scenario_overrides: dict) -> dict:
    """
    scenario_overrides example:
        {"fuel_price_pct_change": 10, "delay_days": 5, "demand_shock_pct": -8}

    Returns a recommendation dict (see contract above) recomputed under the
    scenario, plus the baseline recommendation for side-by-side comparison
    in the dashboard's "what-if" panel.
    """
    baseline_recommendation = get_recommendation(route, horizon_days)

    base_forecast_df = get_forecast(route, horizon_days)
    shocked_forecast_df = _apply_scenario(base_forecast_df, scenario_overrides)
    disruption_score = _get_disruption_score(route)

    # delay days bump disruption risk directly — transparent, not a black box
    disruption_score = float(np.clip(
        disruption_score + scenario_overrides.get("delay_days", 0) * 0.01, 0, 1
    ))

    charter_decision, charter_reason = _select_charter_type(shocked_forecast_df, disruption_score)
    timing_decision, timing_reason = _recommend_timing(shocked_forecast_df, disruption_score)

    band_width = (shocked_forecast_df["upper"] - shocked_forecast_df["lower"]).mean()
    confidence = float(np.clip(1 - band_width / shocked_forecast_df["forecast"].mean(), 0, 1))

    return {
        "route": route,
        "as_of_date": datetime.today().date().isoformat(),
        "charter_decision": charter_decision,
        "timing_decision": timing_decision,
        "disruption_score": round(disruption_score, 3),
        "confidence": round(confidence, 3),
        "reasoning": f"{charter_reason} {timing_reason}",
        "scenario_applied": scenario_overrides,
        "baseline_recommendation": baseline_recommendation,
    }


def estimate_savings(route: str, lookback_days: int = 90) -> dict:
    """
    Backtest-style comparison: 'always charter spot at current rate' (naive
    baseline) vs. our recommended strategy, over `lookback_days` of history.

    NOTE: this is a simplified backtest for demo purposes — it re-uses the
    forecast generator to stand in for historical actuals until the Data
    Lead's real historical dataset is wired in. Swap `_historical_rates()`
    for a real query against data/processed/ once available.
    """
    history_df = _historical_rates(route, lookback_days)

    # Naive baseline: charter spot every day at that day's rate + a flat spot premium
    spot_premium = 1.02
    naive_cost = float((history_df["rate"] * spot_premium).sum())

    # "Optimized" cost: simulate the decision engine choosing spot vs a locked
    # time-charter rate (avg of the period) whichever is cheaper, day by day —
    # a simple, defensible proxy for "our strategy would have paid this much"
    time_charter_rate = float(history_df["rate"].mean()) * 0.97  # locked-in discount
    optimized_daily = np.minimum(history_df["rate"].values, time_charter_rate)
    optimized_cost = float(optimized_daily.sum())

    savings_amount = naive_cost - optimized_cost
    savings_pct = (savings_amount / naive_cost * 100) if naive_cost else 0.0

    return {
        "route": route,
        "lookback_days": lookback_days,
        "naive_cost": round(naive_cost, 2),
        "optimized_cost": round(optimized_cost, 2),
        "savings_amount": round(savings_amount, 2),
        "savings_pct": round(savings_pct, 2),
    }


def _historical_rates(route: str, lookback_days: int) -> pd.DataFrame:
    """
    MOCK historical data. Replace this with a real read from
    data/processed/ (the Data Lead's consolidated dataset) as soon as it
    lands — keep the return shape [date, rate] identical.
    """
    rng = np.random.default_rng(abs(hash(route)) % (2**32))
    dates = pd.date_range(end=datetime.today().date() - timedelta(days=1), periods=lookback_days, freq="D")
    base_rate = 18000.0
    noise = rng.normal(0, base_rate * 0.05, lookback_days)
    trend = np.linspace(-base_rate * 0.05, base_rate * 0.05, lookback_days)
    rates = base_rate + trend + noise
    return pd.DataFrame({"date": dates, "rate": rates})


# --------------------------------------------------------------------------
# 5. QUICK SELF-TEST — run `python pipeline.py` to sanity-check the whole
#    pipeline end to end without needing the dashboard at all.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    ROUTE = "Vizag-Capesize-IronOre"

    print("\n=== get_forecast ===")
    fc = get_forecast(ROUTE, horizon_days=14)
    print(fc.head())

    print("\n=== get_recommendation ===")
    rec = get_recommendation(ROUTE, horizon_days=14)
    for k, v in rec.items():
        print(f"  {k}: {v}")

    print("\n=== run_scenario ===")
    scenario = run_scenario(
        ROUTE,
        horizon_days=14,
        scenario_overrides={"fuel_price_pct_change": 12, "delay_days": 6, "demand_shock_pct": -5},
    )
    for k, v in scenario.items():
        if k != "baseline_recommendation":
            print(f"  {k}: {v}")

    print("\n=== estimate_savings ===")
    savings = estimate_savings(ROUTE, lookback_days=90)
    for k, v in savings.items():
        print(f"  {k}: {v}")