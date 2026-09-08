# Freight Forecasting & Charter Decision Engine (Ministry of Steel)

An end-to-end intelligent maritime analytics and procurement decision engine built for the Ministry of Steel, Government of India. Designed to transition bulk raw material logistics (coking coal, thermal coal, iron ore) from volatile day-to-day spot fixtures to optimized multi-voyage and period charters (COA / Time Charter).

## Core Modules (ML Engineer #2 — NLP & Decision Logic)

- **`src/nlp/`**: Real-time maritime disruption intelligence engine (Bay of Bengal cyclones, dockworker strikes, draft siltation, bunker fuel price spikes) converting text alerts into normalized disruption scores and ML feature vectors.
- **`src/optimizer/`**: Physical port constraint solver modeling Indian East Coast discharge ports (Paradip, Vizag Inner/Outer, Gangavaram, Dhamra, Gopalpur, Haldia, Sandheads) and global loading origins across Handysize, Supramax, Panamax, and Capesize bulk carriers.
- **`src/decision/`**: Strategic charter-type selector (Spot vs Period vs COA), "Buy Now vs Wait" market timing recommender, and interactive scenario simulator.
- **`src/pipeline.py`**: Unified orchestrator providing typed Pydantic payloads for backend and dashboard layers.

## Key Documentation

1. [**`PROJECT_ARCHITECTURE_AND_MODELS.md`**](./PROJECT_ARCHITECTURE_AND_MODELS.md): Complete architecture blueprint, mathematical formulations, port specifications matrix, and operational decision trees.
2. [**`INTEGRATION_GUIDE_FOR_5_ENGINEERS.md`**](./INTEGRATION_GUIDE_FOR_5_ENGINEERS.md): Detailed handoff playbooks, JSON schemas, and code integration templates for Data Lead, Feature Engineer, ML Engineer #1, Backend Dev, and Dashboard Dev.

## Quick Start & Verification

```bash
# 1. Run automated unit test suite (18 tests)
python3 -m unittest discover -s tests -v

# 2. Run the interactive 3-minute demonstration
python3 run_demo.py
```
