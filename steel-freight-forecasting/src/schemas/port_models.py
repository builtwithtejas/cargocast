from enum import Enum
from typing import List, Optional
from .base import BaseModel, Field

class VesselClass(str, Enum):
    HANDYSIZE = 'Handysize'
    SUPRAMAX = 'Supramax'
    PANAMAX = 'Panamax'
    CAPESIZE = 'Capesize'

class PortType(str, Enum):
    DISCHARGE = 'discharge'
    LOADING = 'loading'
    TRANSSHIPMENT_LIGHTERAGE = 'transshipment_lighterage'

class PortInfrastructure(BaseModel):
    port_id: str
    port_name: str
    country: str = 'India'
    region: Optional[str] = 'East Coast India'
    coast: Optional[str] = None
    state: Optional[str] = None
    port_type: PortType
    max_draft_meters: float
    max_loa_meters: float
    max_beam_meters: float
    permissible_vessel_types: List[VesselClass]
    daily_discharge_rate_mt: Optional[float] = None
    daily_loading_rate_mt: Optional[float] = None
    tidal_restriction: bool = False
    requires_lighterage_for_cape: bool = False
    berth_count_dry_bulk: Optional[int] = None
    typical_waiting_time_days: float = 2.0
    demurrage_rate_usd_day: float = 20000.0
    lighterage_anchorage_id: Optional[str] = None
    lighterage_cost_usd_mt: float = 0.0
    typical_sailing_days_to_east_coast_india: Optional[int] = None
    sailing_distance_nm: Optional[int] = None
    commodity_focus: Optional[List[str]] = None
    notes: Optional[str] = None

class VesselSpecification(BaseModel):
    class_name: VesselClass
    min_dwt: float
    max_dwt: float
    nominal_cargo_intake_mt: float
    laden_draft_meters: float
    ballast_draft_meters: float
    length_overall_loa_meters: float
    beam_meters: float
    geared: bool
    fuel_consumption_sea_mt_day: float
    fuel_consumption_port_mt_day: float
    standard_charter_hire_baseline_usd_day: float
