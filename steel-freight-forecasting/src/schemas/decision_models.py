from enum import Enum
from typing import List, Optional, Dict
from .base import BaseModel, Field
from .port_models import VesselClass
from .disruption_models import DisruptionSeverity

class CharterType(str, Enum):
    SPOT_VOYAGE = 'SPOT_VOYAGE'
    SHORT_TERM_PERIOD = 'SHORT_TERM_PERIOD'  # 3 to 6 months
    MEDIUM_TERM_PERIOD = 'MEDIUM_TERM_PERIOD' # 12 to 24 months
    COA_CONTRACT_OF_AFFREIGHTMENT = 'COA_CONTRACT_OF_AFFREIGHTMENT' # Multi-voyage volume contract

class TimingAction(str, Enum):
    ENTER_IMMEDIATE = 'ENTER_IMMEDIATE'       # 0 to 3 days
    ACCUMULATE_STAGGERED = 'ACCUMULATE_STAGGERED' # 1 to 2 weeks
    DEFER_AND_WAIT = 'DEFER_AND_WAIT'         # 2 to 4 weeks
    HEDGE_FFA_OR_COA = 'HEDGE_FFA_OR_COA'     # Extreme volatility hedging

class VesselSuitabilityResult(BaseModel):
    vessel_class: VesselClass
    is_feasible: bool
    draft_margin_meters: float
    loa_margin_meters: float
    beam_margin_meters: float
    requires_lighterage: bool
    lighterage_cost_usd_mt: float
    deadweight_utilization_pct: float
    daily_discharge_rate_mt: float
    estimated_port_turnaround_days: float
    total_voyage_freight_usd_mt: float
    warnings: List[str] = Field(default_factory=list)

class CharterRecommendation(BaseModel):
    route_id: str
    origin_port: str
    discharge_port: str
    commodity: str
    cargo_parcel_size_mt: float
    recommended_charter_type: CharterType
    recommended_timing: TimingAction
    optimal_vessel_class: VesselClass
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    current_spot_rate_usd_mt: float
    forecast_30d_rate_usd_mt: float
    expected_landed_cost_usd_mt: float
    expected_landed_cost_inr_mt: float
    potential_savings_vs_spot_pct: float
    executive_reasoning: str
    key_drivers: List[str]
    disruption_severity: DisruptionSeverity
    hedge_recommendation: Optional[str] = None
    vessel_options_evaluated: List[VesselSuitabilityResult]

class ScenarioShockInput(BaseModel):
    fuel_price_pct_shock: float = Field(0.0, description='Percentage shift in bunker fuel price e.g. +10.0 for +10%')
    weather_cyclone_delay_days: float = Field(0.0, description='Additional days delayed due to cyclone or weather')
    cargo_demand_pct_shock: float = Field(0.0, description='Percentage change in steel plant demand e.g. +15.0')
    port_congestion_delay_days: float = Field(0.0, description='Additional berthing queue days at destination port')
    fx_inr_usd_shift: float = Field(0.0, description='Shift in INR/USD exchange rate e.g. +2.0 INR')

class ScenarioSimulationOutput(BaseModel):
    scenario_name: str
    baseline_freight_usd_mt: float
    shocked_freight_usd_mt: float
    freight_delta_usd_mt: float
    freight_delta_pct: float
    baseline_freight_inr_mt: float
    shocked_freight_inr_mt: float
    freight_delta_inr_mt: float
    fuel_cost_impact_usd_mt: float
    demurrage_impact_usd_mt: float
    market_tightness_impact_usd_mt: float
    recommended_charter_type_baseline: CharterType
    recommended_charter_type_shocked: CharterType
    recommended_timing_baseline: TimingAction
    recommended_timing_shocked: TimingAction
    strategy_shifted: bool
    plain_language_rationale: str
