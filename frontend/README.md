# CargoCast Web (Option B build)

## Run the backend
    pip install -r requirements.txt
    uvicorn backend.main:app --reload --port 8000

## Run the frontend (separate terminal)
    cd frontend
    python -m http.server 5500

Then open:
- http://127.0.0.1:5500/dashboard.html
- http://127.0.0.1:5500/forecast.html
- http://127.0.0.1:5500/scenarios.html

## What's wired up (all 3 pages, fully live)

**dashboard.html**
- Live Chart.js forecast chart with confidence band (replaces static Stitch SVG)
- Live recommendation panel (charter type, timing, reasoning)
- 3 working scenario sliders -> live chart/recommendation/savings updates
- Live cost-savings cards

**forecast.html**
- Live 180-day Chart.js forecast chart with confidence bands (replaces static SVG)
- Live "PROJECTED 180D TARGET" banner (target price, % change, P95/P05 range)
- NOTE: the "Global Cargo Demand Forecast" bar chart and "Historical vs.
  Predicted" backtest sparkline are still static Stitch mockups -- there's
  no real demand model or backtest endpoint yet. Wire these once ML Eng #1
  has a real demand model and someone computes real backtest accuracy.

**scenarios.html**
- Fuel / Delay / Demand sliders -> live POST to /api/scenario, debounced
- "RUN MONTE CARLO SIMULATION" button also triggers a live run
- Live Base Case vs. Shocked Case comparison chart (Chart.js, replaces
  static SVG)
- Live impact summary + risk badge based on real savings/recommendation output
- 3 preset buttons (Cyclone Season, Fuel Spike, Demand Surge) set the
  sliders to representative values and run the simulation automatically
- NOTE: the "Geopolitical Canal Surcharge" slider and "Cyclone Season"
  toggle are still visual-only -- the backend doesn't model those as
  separate levers yet (cyclone risk is folded into delay_days for now).
  Export buttons (CSV/PDF/JSON) are also still static.

## Backend endpoints
- GET  /api/health
- GET  /api/forecast?horizon_days=60        (dashboard uses 60, forecast page uses 180, scenarios uses 90)
- GET  /api/recommendation?horizon_days=60
- GET  /api/disruption-score
- POST /api/scenario?horizon_days=60   body: {fuel_pct_change, delay_days, demand_shock_pct, cargo_tonnage, usd_to_inr}
- GET  /api/savings?horizon_days=60

## Swapping in real teammate data
backend/pipeline.py has one function per pipeline stage (get_forecast,
get_recommendation, run_scenario, estimate_savings, get_disruption_score).
Each one is documented with which teammate's real module should replace
the mock body. The FastAPI layer (backend/main.py) and all 3 frontend
pages never need to change -- only pipeline.py's internals do.
