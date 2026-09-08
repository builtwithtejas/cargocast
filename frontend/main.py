"""
CargoCast FastAPI backend.

Serves the forecasting/decision/scenario/savings pipeline as JSON so the
Stitch-generated frontend (plain HTML + JS) can fetch live data instead
of hardcoded numbers.

Run with:  uvicorn backend.main:app --reload --port 8000
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .pipeline import (
    get_forecast,
    get_recommendation,
    run_scenario,
    estimate_savings,
    get_disruption_score,
)

app = FastAPI(title="CargoCast API")

# CORS: wide open for hackathon dev (frontend is likely served from a
# different port/origin, e.g. a static file server on :5500 or :3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    fuel_pct_change: float = 0.0
    delay_days: float = 0.0
    demand_shock_pct: float = 0.0
    cargo_tonnage: int = 150_000
    usd_to_inr: float = 83.5


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/forecast")
def api_forecast(horizon_days: int = Query(60, ge=7, le=180)):
    df = get_forecast(horizon_days=horizon_days)
    return {
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "forecast": df["forecast"].round(2).tolist(),
        "lower": df["lower"].round(2).tolist(),
        "upper": df["upper"].round(2).tolist(),
    }


@app.get("/api/disruption-score")
def api_disruption_score():
    return {"disruption_score": get_disruption_score()}


@app.get("/api/recommendation")
def api_recommendation(horizon_days: int = Query(60, ge=7, le=180)):
    df = get_forecast(horizon_days=horizon_days)
    score = get_disruption_score()
    rec = get_recommendation(df, disruption_score=score)
    return rec


@app.post("/api/scenario")
def api_scenario(req: ScenarioRequest, horizon_days: int = Query(60, ge=7, le=180)):
    base_df = get_forecast(horizon_days=horizon_days)
    score = get_disruption_score()

    scenario_df = run_scenario(
        base_df,
        fuel_pct_change=req.fuel_pct_change,
        delay_days=req.delay_days,
        demand_shock_pct=req.demand_shock_pct,
    )

    rec = get_recommendation(scenario_df, disruption_score=score)
    savings = estimate_savings(
        scenario_df, rec,
        cargo_tonnage=req.cargo_tonnage,
        usd_to_inr=req.usd_to_inr,
    )

    return {
        "base_forecast": {
            "dates": base_df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "forecast": base_df["forecast"].round(2).tolist(),
            "lower": base_df["lower"].round(2).tolist(),
            "upper": base_df["upper"].round(2).tolist(),
        },
        "scenario_forecast": {
            "dates": scenario_df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "forecast": scenario_df["forecast"].round(2).tolist(),
            "lower": scenario_df["lower"].round(2).tolist(),
            "upper": scenario_df["upper"].round(2).tolist(),
        },
        "recommendation": rec,
        "savings": savings,
    }


@app.get("/api/savings")
def api_savings(
    horizon_days: int = Query(60, ge=7, le=180),
    cargo_tonnage: int = 150_000,
    usd_to_inr: float = 83.5,
):
    df = get_forecast(horizon_days=horizon_days)
    score = get_disruption_score()
    rec = get_recommendation(df, disruption_score=score)
    savings = estimate_savings(df, rec, cargo_tonnage=cargo_tonnage, usd_to_inr=usd_to_inr)
    return savings
