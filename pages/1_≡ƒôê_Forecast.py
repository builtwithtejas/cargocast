
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from backend.pipeline import get_forecast
ROOT=Path(__file__).resolve().parents[1]
ui=components.declare_component("cargocast_forecast_ui", path=str(ROOT/"cargocast_component"/"forecast"))
@st.cache_data(ttl=600)
def data():
    df=get_forecast("Vizag-Capesize-IronOre",180)
    return {"dates":df.date.dt.strftime("%Y-%m-%d").tolist(),"forecast":df.forecast.round(2).tolist(),"lower":df.lower.round(2).tolist(),"upper":df.upper.round(2).tolist()}
st.set_page_config(page_title="CargoCast Forecast",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st.markdown("<style>[data-testid='stSidebar'],[data-testid='stHeader'],#MainMenu,footer{display:none!important}.block-container{padding:0!important;max-width:none!important}</style>",unsafe_allow_html=True)
ui(page="forecast",forecast=data())
