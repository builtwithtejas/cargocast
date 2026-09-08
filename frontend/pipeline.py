"""
CargoCast backend pipeline.

This module is the single integration point between all ML/decision logic
and the Streamlit dashboard. Right now every function returns realistic
MOCK data so the dashboard can be built and demoed independently of the
rest of the pipeline being finished.

HOW THIS GETS REPLACED WITH REAL DATA:
Each teammate's real module should expose a function with the SAME NAME
and SAME RETURN SHAPE as the mock function below. Once real modules exist,
swap the mock function body for a real import + call — the dashboard
(dashboard/app.py) never needs to change because it only ever calls these
four functions.

    models/forecasting.py          -> get_forecast()
    decision_engine/*.py           -> get_recommendation()
    decision_engine/scenario_simulator.py -> run_scenario()
    backend/pipeline.py (own logic) -> estimate_savings()
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# 1. FORECAST
# ---------------------------------------------------------------------------
def get_forecast(horizon_days: int = 60) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: date, forecast, lower, upper
    representing the predicted freight rate (USD/tonne) with a
    quantile-regression confidence band.

    Real version: ML Engineer #1's models/forecasting.py + quantile_regression.py
    """
    rng = np.random.default_rng(42)
    start = datetime.today()
    dates = [start + timedelta(days=i) for i in range(horizon_days)]

    # simple synthetic trend + noise, standing in for a real BCI/BPI forecast
    base = 18.5  # USD/tonne baseline freight rate
    trend = np.linspace(0, 2.2, horizon_days)  # gentle upward drift
    seasonal = 0.8 * np.sin(np.linspace(0, 3 * np.pi, horizon_days))
    noise = rng.normal(0, 0.3, horizon_days)
    forecast = base + trend + seasonal + noise

    # uncertainty band widens further into the future (realistic)
    band_width = np.linspace(0.6, 2.5, horizon_days)

    return pd.DataFrame({
        "date": dates,
        "forecast": forecast,
        "lower": forecast - band_width,
        "upper": forecast + band_width,
    })


# ---------------------------------------------------------------------------
# 2. RECOMMENDATION
# ---------------------------------------------------------------------------
def get_recommendation(forecast_df: pd.DataFrame, disruption_score: float = 0.3) -> dict:
    """
    Returns a dict describing the charter-type and timing recommendation.

    Real version: ML Engineer #2's decision_engine/charter_selector.py
    and decision_engine/timing_recommender.py, combined with the NLP
    disruption score from nlp/disruption_scoring.py.
    """
    early_avg = forecast_df["forecast"].iloc[:10].mean()
    late_avg = forecast_df["forecast"].iloc[-10:].mean()
    trend_pct = (late_avg - early_avg) / early_avg * 100

    band_width_avg = (forecast_df["upper"] - forecast_df["lower"]).mean()
    high_volatility = band_width_avg > 3.0

    if trend_pct > 3 and disruption_score < 0.5:
        charter_type = "Time-Charter"
        timing = "Buy Now"
        reason = (
            f"Rates trending up (+{trend_pct:.1f}% over horizon) with low disruption "
            f"risk ({disruption_score:.0%}). Locking in a time-charter now avoids "
            f"paying higher spot rates later."
        )
    elif high_volatility or disruption_score > 0.5:
        charter_type = "Spot"
        timing = "Wait"
        reason = (
            f"High forecast uncertainty or elevated disruption risk "
            f"({disruption_score:.0%}). Staying on spot preserves flexibility "
            f"until conditions stabilize."
        )
    else:
        charter_type = "Spot"
        timing = "Buy Now"
        reason = (
            f"Rates relatively flat ({trend_pct:+.1f}%) with manageable risk. "
            f"Spot chartering now is cost-efficient without long-term commitment."
        )

    return {
        "charter_type": charter_type,
        "timing": timing,
        "trend_pct": round(trend_pct, 2),
        "disruption_score": disruption_score,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# 3. SCENARIO SIMULATOR
# ---------------------------------------------------------------------------
def run_scenario(
    forecast_df: pd.DataFrame,
    fuel_pct_change: float = 0.0,
    delay_days: int = 0,
    demand_shock_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Applies user-controlled scenario shocks to the base forecast and
    returns a modified forecast DataFrame with the same shape as
    get_forecast(). Used to power the dashboard's scenario sliders.

    Real version: decision_engine/scenario_simulator.py
    """
    scenario_df = forecast_df.copy()

    # fuel price shock: bunker fuel is a large % of charter cost
    fuel_effect = fuel_pct_change / 100 * 0.35  # ~35% cost sensitivity to fuel
    scenario_df["forecast"] *= (1 + fuel_effect)
    scenario_df["lower"] *= (1 + fuel_effect)
    scenario_df["upper"] *= (1 + fuel_effect)

    # port/route delay: adds cost pressure + widens uncertainty
    if delay_days > 0:
        delay_effect = delay_days * 0.01  # 1% per delay day, simple linear proxy
        scenario_df["forecast"] *= (1 + delay_effect)
        widen = delay_days * 0.05
        scenario_df["lower"] -= widen
        scenario_df["upper"] += widen

    # demand shock: shifts the whole curve up/down
    demand_effect = demand_shock_pct / 100 * 0.5
    scenario_df["forecast"] *= (1 + demand_effect)
    scenario_df["lower"] *= (1 + demand_effect)
    scenario_df["upper"] *= (1 + demand_effect)

    return scenario_df


# ---------------------------------------------------------------------------
# 4. COST SAVINGS ESTIMATOR
# ---------------------------------------------------------------------------
def estimate_savings(
    forecast_df: pd.DataFrame,
    recommendation: dict,
    cargo_tonnage: int = 150_000,
    usd_to_inr: float = 83.5,
) -> dict:
    """
    Compares the recommended strategy's expected cost against a naive
    baseline (always charter spot at day-1 rate) and returns the
    estimated savings in INR.

    Real version: backend/pipeline.py owns this logic once real
    forecasts/recommendations exist -- the calculation itself doesn't
    change, only its inputs do.

    Baseline definition: "naive" = a procurement team with no forecasting
    tool, charters reactively whenever cargo is needed -- approximated as
    the AVERAGE rate across the horizon (no ability to time the market).
    The model strategy uses the recommended timing to do better than that
    average, e.g. locking in early during a rising trend, or waiting out
    a dip.
    """
    naive_rate = forecast_df["forecast"].mean()
    naive_total_cost_usd = naive_rate * cargo_tonnage

    if recommendation["timing"] == "Buy Now":
        # locks in near-term rate rather than waiting through the full horizon
        effective_rate = forecast_df["forecast"].iloc[:10].mean()
    else:
        # "Wait": times the purchase near the forecasted low point
        effective_rate = forecast_df["forecast"].iloc[:30].min()

    model_total_cost_usd = effective_rate * cargo_tonnage
    savings_usd = naive_total_cost_usd - model_total_cost_usd
    savings_inr = savings_usd * usd_to_inr

    return {
        "naive_cost_usd": round(naive_total_cost_usd, 2),
        "model_cost_usd": round(model_total_cost_usd, 2),
        "savings_usd": round(savings_usd, 2),
        "savings_inr": round(savings_inr, 2),
        "savings_pct": round((savings_usd / naive_total_cost_usd) * 100, 2),
    }


# ---------------------------------------------------------------------------
# 5. DISRUPTION SCORE (used as an input to get_recommendation)
# ---------------------------------------------------------------------------
def get_disruption_score() -> float:
    """
    Returns a 0-1 disruption risk score derived from recent shipping news.

    Real version: nlp/disruption_scoring.py (VADER sentiment over
    scraped shipping news headlines).
    """
    # mock: moderate baseline risk
    return 0.32
