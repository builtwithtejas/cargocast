"""CargoCast Streamlit dashboard for Hugging Face Spaces."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from backend.pipeline import get_forecast, get_recommendation, run_scenario, estimate_savings

st.set_page_config(
    page_title="CargoCast | Freight Intelligence",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 CargoCast")
st.caption("Intelligent freight forecasting and charter decision support")

with st.sidebar:
    st.header("Scenario controls")
    route = st.selectbox(
        "Route",
        [
            "Vizag-Capesize-IronOre",
            "Paradip-Capesize-IronOre",
            "Haldia-Capesize-IronOre",
        ],
        index=0,
    )
    horizon = st.slider("Forecast horizon (days)", 7, 60, 30)
    st.divider()
    fuel = st.slider("Fuel price change (%)", -20, 30, 0)
    delay = st.slider("Port / route delay (days)", 0, 15, 0)
    demand = st.slider("Demand shock (%)", -20, 20, 0)
    cargo = st.number_input("Cargo tonnage", min_value=10_000, max_value=1_000_000, value=150_000, step=10_000)
    usd_inr = st.number_input("USD/INR", min_value=50.0, max_value=150.0, value=83.5, step=0.5)

@st.cache_data(ttl=300)
def load_forecast(route_name: str, days: int) -> pd.DataFrame:
    return get_forecast(route_name, days)

@st.cache_data(ttl=300)
def load_recommendation(route_name: str, days: int) -> dict:
    return get_recommendation(route_name, days)

try:
    forecast = load_forecast(route, horizon)
    rec = load_recommendation(route, horizon)
except Exception as exc:
    st.error(f"CargoCast could not load the forecasting layer: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest forecast", f"{forecast['forecast'].iloc[0]:,.2f}")
c2.metric("Upper bound", f"{forecast['upper'].iloc[0]:,.2f}")
c3.metric("Disruption score", f"{rec['disruption_score']:.2f}")
c4.metric("Confidence", f"{rec['confidence']:.0%}")

st.subheader("Freight rate forecast")
chart_df = forecast.set_index("date")[['forecast', 'lower', 'upper']]
st.line_chart(chart_df, height=380)

st.subheader("Recommendation")
r1, r2 = st.columns(2)
with r1:
    st.success(f"Charter: **{rec['charter_decision']}**")
with r2:
    st.info(f"Timing: **{rec['timing_decision']}**")
st.write(rec["reasoning"])

st.subheader("What-if scenario")
scenario_values = {
    "fuel_price_pct_change": float(fuel),
    "delay_days": float(delay),
    "demand_shock_pct": float(demand),
}
try:
    scenario = run_scenario(route, horizon, scenario_values)
    if any(v != 0 for v in scenario_values.values()):
        st.write("Scenario recommendation:")
        s1, s2, s3 = st.columns(3)
        s1.metric("Charter", scenario["charter_decision"])
        s2.metric("Timing", scenario["timing_decision"])
        s3.metric("Disruption", f"{scenario['disruption_score']:.2f}")
        st.write(scenario["reasoning"])
    else:
        st.caption("Move the scenario sliders to stress-test fuel, delay, and demand assumptions.")
except Exception as exc:
    st.warning(f"Scenario simulation unavailable: {exc}")

st.subheader("Savings estimate")
try:
    savings = estimate_savings(route, 90)
    s1, s2, s3 = st.columns(3)
    s1.metric("Naive cost", f"₹{savings['naive_cost']:,.0f}")
    s2.metric("Optimized cost", f"₹{savings['optimized_cost']:,.0f}")
    s3.metric("Estimated savings", f"₹{savings['savings_amount']:,.0f}", f"{savings['savings_pct']:.2f}%")
    st.caption("Savings is a simplified demo/backtest estimate based on the current backend implementation.")
except Exception as exc:
    st.warning(f"Savings estimator unavailable: {exc}")
