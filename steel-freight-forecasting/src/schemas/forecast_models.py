from enum import Enum
from typing import List, Optional
from .base import BaseModel, Field

class TrendDirection(str, Enum):
    UPWARD = 'UPWARD'
    DOWNWARD = 'DOWNWARD'
    SIDEWAYS = 'SIDEWAYS'

class VolatilityRegime(str, Enum):
    LOW = 'LOW'
    MODERATE = 'MODERATE'
    HIGH = 'HIGH'
    MODERATE_TO_HIGH = 'MODERATE_TO_HIGH'

class HorizonForecast(BaseModel):
    horizon_days: int
    q10: float = Field(..., description='10th percentile rate forecast (bearish band) in USD/MT')
    q50: float = Field(..., description='Median rate forecast (point prediction) in USD/MT')
    q90: float = Field(..., description='90th percentile rate forecast (bullish band) in USD/MT')
    tce_usd_day: float = Field(..., description='Time Charter Equivalent daily hire rate in USD/day')

class RouteForecast(BaseModel):
    route_id: str
    origin_port_id: str
    discharge_port_id: str
    vessel_class: str
    commodity: str
    current_spot_rate_usd_mt: float
    current_time_charter_usd_day: float
    forecast_horizons: List[HorizonForecast]
    trend_slope_usd_day: float
    trend_direction: TrendDirection
    volatility_regime: VolatilityRegime
    cargo_demand_monthly_mt: float

class ForecastFeed(BaseModel):
    as_of_date: str
    base_bdi: float = Field(..., description='Baltic Dry Index')
    base_bci: float = Field(..., description='Baltic Capesize Index')
    base_bpi: float = Field(..., description='Baltic Panamax Index')
    base_bsi: float = Field(..., description='Baltic Supramax Index')
    base_bunker_vlsfo_usd_mt: float
    base_inr_usd_fx_rate: float
    routes: List[RouteForecast]
