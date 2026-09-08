import math
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from src.schemas.base import BaseModel, Field
from src.schemas.port_models import VesselClass

class TidePhaseResult(BaseModel):
    date_str: str
    lunar_day: int
    tide_phase: str # 'SPRING_TIDE', 'NEAP_TIDE', 'MID_TIDE'
    base_channel_draft_meters: float
    monsoon_siltation_penalty_meters: float
    effective_max_draft_meters: float
    vessel_laden_draft_meters: float
    requires_lighterage: bool
    lighterage_tonnage_mt: float
    lighterage_share_pct: float
    lighterage_surcharge_usd_mt: float
    recommended_anchorage: str
    operational_advice: str

class TidalDraftCalculator:
    """
    Simulates tidal curves and seasonal siltation for riverine and draft-restricted
    East Coast Indian ports (Haldia Dock Complex / Hooghly Estuary & Vizag Inner).
    Predicts exact lighterage volume required at Sagar / Sandheads anchorage.
    """
    def __init__(self):
        # Haldia River Baseline Parameters
        self.spring_draft_max = 8.80 # meters during peak spring tides
        self.neap_draft_min = 7.30   # meters during low neap tides
        self.lighterage_unit_cost = 5.75 # USD/MT standard barging & offshore crane rate

    def calculate_lunar_day(self, dt: datetime) -> int:
        """
        Approximate lunar day (0 to 29) using synodic month (~29.53 days).
        Reference new moon: 2026-08-12.
        """
        ref_new_moon = datetime(2026, 8, 12)
        diff_days = (dt - ref_new_moon).total_seconds() / 86400.0
        lunar_day = int(diff_days % 29.53)
        return lunar_day

    def evaluate_haldia_arrival_draft(
        self,
        arrival_date_str: str,
        vessel_class: VesselClass,
        cargo_parcel_mt: float,
        vessel_draft_m: float = 12.8 # default Supramax laden draft
    ) -> TidePhaseResult:
        try:
            dt = datetime.strptime(arrival_date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime(2026, 9, 2)

        lunar_day = self.calculate_lunar_day(dt)

        # Spring tides occur around New Moon (day 0/29) and Full Moon (day 14/15)
        # Neap tides occur around 1st Quarter (day 7/8) and 3rd Quarter (day 21/22)
        tide_oscillation = math.cos(2.0 * math.pi * (lunar_day / 14.765))
        # Maps oscillation from [-1, 1] to [neap_draft_min, spring_draft_max]
        mid_draft = (self.spring_draft_max + self.neap_draft_min) / 2.0
        amplitude = (self.spring_draft_max - self.neap_draft_min) / 2.0
        base_draft = mid_draft + (amplitude * tide_oscillation)

        # Determine tide category
        if tide_oscillation > 0.4:
            tide_phase = "SPRING_TIDE (High Water Window)"
        elif tide_oscillation < -0.4:
            tide_phase = "NEAP_TIDE (Restricted Water Window)"
        else:
            tide_phase = "MID_TIDE (Moderate Draft Window)"

        # Monsoon siltation penalty (July to October is heavy monsoon runoff)
        month = dt.month
        if month in [7, 8, 9, 10]:
            siltation_penalty = 0.45 # meters lost to silt banks at Auckland/Jellingham
        elif month in [5, 6, 11]:
            siltation_penalty = 0.20
        else:
            siltation_penalty = 0.05

        effective_draft = round(base_draft - siltation_penalty, 2)

        # Lighterage calculation at Sandheads
        excess_draft_m = max(0.0, vessel_draft_m - effective_draft)
        requires_lighterage = excess_draft_m > 0.0

        if requires_lighterage:
            # TPC (Tonnes per Centimeter) immersion approximation
            tpc = (cargo_parcel_mt / 1000.0) * 0.70
            excess_draft_cm = excess_draft_m * 100.0
            lighter_tons = min(cargo_parcel_mt * 0.60, excess_draft_cm * tpc)
            lighter_share = round((lighter_tons / cargo_parcel_mt) * 100.0, 1)
            lighter_cost_mt = round((lighter_tons * self.lighterage_unit_cost) / cargo_parcel_mt, 2)
            
            advice = (
                f"River draft restricted to {effective_draft:.2f}m ({tide_phase}). "
                f"Vessel requires {lighter_tons:,.0f} MT ({lighter_share}%) lightered at Sandheads Anchorage "
                f"before river transit to Haldia Lock."
            )
        else:
            lighter_tons = 0.0
            lighter_share = 0.0
            lighter_cost_mt = 0.0
            advice = f"Favorable tide ({effective_draft:.2f}m). Direct river navigation permissible to Haldia berth."

        return TidePhaseResult(
            date_str=arrival_date_str,
            lunar_day=lunar_day,
            tide_phase=tide_phase,
            base_channel_draft_meters=round(base_draft, 2),
            monsoon_siltation_penalty_meters=siltation_penalty,
            effective_max_draft_meters=effective_draft,
            vessel_laden_draft_meters=vessel_draft_m,
            requires_lighterage=requires_lighterage,
            lighterage_tonnage_mt=round(lighter_tons, 0),
            lighterage_share_pct=lighter_share,
            lighterage_surcharge_usd_mt=lighter_cost_mt,
            recommended_anchorage="IN_SGR_ANCH (Sagar / Sandheads)",
            operational_advice=advice
        )
