
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from backend.pipeline import get_forecast,run_scenario,_apply_scenario,estimate_savings
ROOT=Path(__file__).resolve().parents[1]
ui=components.declare_component("cargocast_scenarios_ui", path=str(ROOT/"cargocast_component"/"scenarios"))

def pack(df): return {"dates":df.date.dt.strftime("%Y-%m-%d").tolist(),"forecast":df.forecast.round(2).tolist(),"lower":df.lower.round(2).tolist(),"upper":df.upper.round(2).tolist()}
def make(fuel,delay,demand):
    base=get_forecast("Vizag-Capesize-IronOre",90)
    res=run_scenario("Vizag-Capesize-IronOre",90,{"fuel_price_pct_change":float(fuel),"delay_days":float(delay),"demand_shock_pct":float(demand)})
    shock=_apply_scenario(base,{"fuel_price_pct_change":float(fuel),"delay_days":float(delay),"demand_shock_pct":float(demand)})
    s=estimate_savings("Vizag-Capesize-IronOre",90)
    sav={"savings_inr":s["savings_amount"]*83.5,"savings_usd":s["savings_amount"],"savings_pct":s["savings_pct"]}
    rec={"charter_type":"TIME_CHARTER" if res["charter_decision"]=="TIME_CHARTER" else "SPOT","timing":"BUY_NOW" if res["timing_decision"]=="BUY_NOW" else "WAIT","disruption_score":res["disruption_score"]}
    return {"base_forecast":pack(base),"scenario_forecast":pack(shock),"recommendation":rec,"savings":sav}

st.set_page_config(page_title="CargoCast Scenarios",page_icon="⚠️",layout="wide",initial_sidebar_state="collapsed")
st.markdown("<style>[data-testid='stSidebar'],[data-testid='stHeader'],#MainMenu,footer{display:none!important}.block-container{padding:0!important;max-width:none!important}</style>",unsafe_allow_html=True)
if 'sc_values' not in st.session_state: st.session_state.sc_values={"fuel":0,"delay":0,"demand":0}
v=st.session_state.sc_values
ui=ui(page="scenarios",result=make(v['fuel'],v['delay'],v['demand']),values=v,default=None)
if isinstance(ui,dict) and {"fuel","delay","demand"}.issubset(ui): st.session_state.sc_values={"fuel":float(ui['fuel']),"delay":float(ui['delay']),"demand":float(ui['demand'])}; st.rerun()
