
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
component_dir=ROOT/"cargocast_component"
cargo_ui=components.declare_component("cargocast_original_ui", path=str(component_dir/"dashboard"))

from backend.pipeline import get_forecast, get_recommendation, run_scenario, estimate_savings

st.set_page_config(page_title="CargoCast", page_icon="🚢", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>[data-testid='stSidebar'],[data-testid='stHeader'],#MainMenu,footer{display:none!important} .block-container{padding:0!important;max-width:none!important}</style>""", unsafe_allow_html=True)

ROUTE="Vizag-Capesize-IronOre"

def pack_forecast(df):
    return {"dates":df["date"].dt.strftime("%Y-%m-%d").tolist(),"forecast":df["forecast"].round(2).tolist(),"lower":df["lower"].round(2).tolist(),"upper":df["upper"].round(2).tolist()}

def pack_savings(s, usd_inr=83.5):
    return {"naive_cost_usd":s["naive_cost"],"model_cost_usd":s["optimized_cost"],"savings_inr":round(s["savings_amount"]*usd_inr,2),"savings_usd":s["savings_amount"],"savings_pct":s["savings_pct"]}

@st.cache_data(ttl=600)
def base_data(horizon):
    f=get_forecast(ROUTE,horizon); r=get_recommendation(ROUTE,horizon); s=estimate_savings(ROUTE,90)
    # map backend contract to original frontend contract
    trend=((f["forecast"].iloc[-7:].mean()-f["forecast"].iloc[:7].mean())/f["forecast"].iloc[:7].mean()*100)
    rr={"charter_type":"TIME_CHARTER" if r["charter_decision"]=="TIME_CHARTER" else "SPOT","timing":"BUY_NOW" if r["timing_decision"]=="BUY_NOW" else "WAIT","trend_pct":round(trend,2),"disruption_score":r["disruption_score"],"reason":r["reasoning"]}
    return pack_forecast(f),rr,pack_savings(s)

def scenario_data(horizon,fuel,delay,demand):
    result=run_scenario(ROUTE,horizon,{"fuel_price_pct_change":float(fuel),"delay_days":float(delay),"demand_shock_pct":float(demand)})
    base=pack_forecast(get_forecast(ROUTE,horizon))
    shocked=get_forecast(ROUTE,horizon).copy()
    # Reuse exact scenario implementation through result recommendation; to keep chart exact, call backend's internal scenario via run_scenario contract is recommendation-only.
    from backend.pipeline import _apply_scenario
    shocked=_apply_scenario(get_forecast(ROUTE,horizon),{"fuel_price_pct_change":float(fuel),"delay_days":float(delay),"demand_shock_pct":float(demand)})
    sf=pack_forecast(shocked)
    # savings is a demo backtest metric; use the backend estimate consistently
    sav=pack_savings(estimate_savings(ROUTE,90))
    return {"base_forecast":base,"scenario_forecast":sf,"recommendation":{"charter_type":"TIME_CHARTER" if result["charter_decision"]=="TIME_CHARTER" else "SPOT","timing":"BUY_NOW" if result["timing_decision"]=="BUY_NOW" else "WAIT","disruption_score":result["disruption_score"]},"savings":sav}

# Render the original dashboard as a Streamlit custom component.
fuel=st.session_state.get("fuel",0); delay=st.session_state.get("delay",0); demand=st.session_state.get("demand",0)
forecast,rec,savings=base_data(60)
if any([fuel,delay,demand]):
    sc=scenario_data(60,fuel,delay,demand); forecast=sc["scenario_forecast"]; rec={**rec,**sc["recommendation"]}; savings=sc["savings"]
value=cargo_ui(page="dashboard",forecast=forecast,recommendation=rec,savings=savings,scenario_values={"fuel":fuel,"delay":delay,"demand":demand},default=None)
if isinstance(value,dict) and {"fuel","delay","demand"}.issubset(value):
    st.session_state.fuel=int(value["fuel"]); st.session_state.delay=int(value["delay"]); st.session_state.demand=int(value["demand"]); st.rerun()
