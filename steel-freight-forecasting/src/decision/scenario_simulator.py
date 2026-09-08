import math
from typing import Dict, Any, Optional
from src.schemas.decision_models import (
    ScenarioShockInput, ScenarioSimulationOutput, CharterType, TimingAction
)
from src.schemas.forecast_models import RouteForecast, TrendDirection
from src.schemas.disruption_models import PortDisruptionStatus, DisruptionSeverity
from src.schemas.port_models import VesselClass, VesselSpecification
from src.optimizer.port_registry import PortRegistry, VESSEL_SPECS
from .charter_selector import CharterTypeSelector

class ScenarioSimulator:
    """
    Transparent stress-testing engine simulating freight cost, demurrage,
    and charter recommendation shifts under fuel, weather, demand, and congestion shocks.
    """
    def __init__(self, port_registry: Optional[PortRegistry] = None):
        self.registry = port_registry or PortRegistry()
        self.selector = CharterTypeSelector()

    def simulate(
        self,
        scenario_name: str,
        shocks: ScenarioShockInput,
        forecast: RouteForecast,
        vessel_class: VesselClass,
        cargo_parcel_mt: float,
        disruption: PortDisruptionStatus,
        base_bunker_usd_mt: float = 635.0,
        base_fx_inr_usd: float = 87.50
    ) -> ScenarioSimulationOutput:
        v_spec = VESSEL_SPECS[vessel_class]
        origin = self.registry.get_port(forecast.origin_port_id)
        discharge = self.registry.get_port(forecast.discharge_port_id)

        # Baseline Parameters
        distance_nm = origin.sailing_distance_nm if origin else 4500
        speed_knots = 12.5
        round_trip_sea_days = (distance_nm / (speed_knots * 24.0)) * 2.0
        
        load_rate = origin.daily_loading_rate_mt if origin else 45000
        discharge_rate = discharge.daily_discharge_rate_mt if discharge else 30000
        base_port_days = (cargo_parcel_mt / load_rate) + (cargo_parcel_mt / discharge_rate) + discharge.typical_waiting_time_days
        base_voyage_days = round_trip_sea_days + base_port_days

        # Baseline Costs
        base_hire_cost = base_voyage_days * v_spec.standard_charter_hire_baseline_usd_day
        base_sea_fuel = round_trip_sea_days * v_spec.fuel_consumption_sea_mt_day
        base_port_fuel = base_port_days * v_spec.fuel_consumption_port_mt_day
        base_bunker_cost = (base_sea_fuel + base_port_fuel) * base_bunker_usd_mt
        base_port_charges = 180000.0 if vessel_class == VesselClass.CAPESIZE else 120000.0

        total_base_cost = base_hire_cost + base_bunker_cost + base_port_charges
        baseline_freight_usd_mt = total_base_cost / cargo_parcel_mt

        # 1. Fuel Shock Impact
        shocked_bunker_price = base_bunker_usd_mt * (1.0 + (shocks.fuel_price_pct_shock / 100.0))
        delta_bunker_price = shocked_bunker_price - base_bunker_usd_mt
        fuel_cost_impact = (base_sea_fuel + base_port_fuel) * delta_bunker_price
        fuel_impact_usd_mt = fuel_cost_impact / cargo_parcel_mt

        # 2. Delay & Demurrage Shock (Weather + Congestion)
        total_delay_days = shocks.weather_cyclone_delay_days + shocks.port_congestion_delay_days
        demurrage_rate = discharge.demurrage_rate_usd_day if discharge else 22000.0
        total_demurrage_cost = total_delay_days * demurrage_rate
        demurrage_impact_usd_mt = total_demurrage_cost / cargo_parcel_mt

        # 3. Demand Shock & Market Tightness
        # Bulk shipping freight rate elasticity to demand shock ~ 0.45
        demand_elasticity = 0.45
        market_tightness_pct = (shocks.cargo_demand_pct_shock / 100.0) * demand_elasticity
        market_tightness_impact_usd_mt = baseline_freight_usd_mt * market_tightness_pct

        # 4. Shocked Freight Total
        shocked_freight_usd_mt = (
            baseline_freight_usd_mt +
            fuel_impact_usd_mt +
            demurrage_impact_usd_mt +
            market_tightness_impact_usd_mt
        )
        freight_delta_usd_mt = shocked_freight_usd_mt - baseline_freight_usd_mt
        freight_delta_pct = (freight_delta_usd_mt / baseline_freight_usd_mt) * 100.0

        # FX Impact
        shocked_fx = base_fx_inr_usd + shocks.fx_inr_usd_shift
        baseline_freight_inr_mt = baseline_freight_usd_mt * base_fx_inr_usd
        shocked_freight_inr_mt = shocked_freight_usd_mt * shocked_fx
        freight_delta_inr_mt = shocked_freight_inr_mt - baseline_freight_inr_mt

        # 5. Recommendation Shift Analysis
        # Baseline Recommendation
        rec_baseline = CharterType.SPOT_VOYAGE
        timing_baseline = TimingAction.ENTER_IMMEDIATE
        if forecast.trend_direction == TrendDirection.UPWARD and cargo_parcel_mt >= 100000:
            rec_baseline = CharterType.COA_CONTRACT_OF_AFFREIGHTMENT
        elif forecast.trend_direction == TrendDirection.DOWNWARD:
            timing_baseline = TimingAction.DEFER_AND_WAIT

        # Shocked Recommendation
        rec_shocked = rec_baseline
        timing_shocked = timing_baseline

        if shocks.weather_cyclone_delay_days >= 3.0 or shocks.port_congestion_delay_days >= 4.0:
            rec_shocked = CharterType.SPOT_VOYAGE
            timing_shocked = TimingAction.DEFER_AND_WAIT
        elif shocks.fuel_price_pct_shock >= 20.0 or shocks.cargo_demand_pct_shock >= 15.0:
            rec_shocked = CharterType.COA_CONTRACT_OF_AFFREIGHTMENT if cargo_parcel_mt >= 80000 else CharterType.SHORT_TERM_PERIOD
            timing_shocked = TimingAction.ENTER_IMMEDIATE

        strategy_shifted = (rec_baseline != rec_shocked) or (timing_baseline != timing_shocked)

        # Plain language explanation
        reasons = []
        if abs(shocks.fuel_price_pct_shock) > 0.01:
            reasons.append(f"Fuel shock of {shocks.fuel_price_pct_shock:+.1f}% altered bunker cost by ${fuel_impact_usd_mt:+.2f}/MT.")
        if total_delay_days > 0.01:
            reasons.append(f"{total_delay_days:.1f} days operational delay contributed ${demurrage_impact_usd_mt:+.2f}/MT in vessel demurrage/idle hire.")
        if abs(shocks.cargo_demand_pct_shock) > 0.01:
            reasons.append(f"Steel production demand shock of {shocks.cargo_demand_pct_shock:+.1f}% adjusted spot market freight by ${market_tightness_impact_usd_mt:+.2f}/MT.")
        if abs(shocks.fx_inr_usd_shift) > 0.01:
            reasons.append(f"FX shift of {shocks.fx_inr_usd_shift:+.2f} INR/USD moved landed cost to ₹{shocked_freight_inr_mt:,.0f}/MT.")

        if strategy_shifted:
            reasons.append(f"STRATEGY SHIFT TRIGGERED: Recommended action shifted from {rec_baseline.value} ({timing_baseline.value}) to {rec_shocked.value} ({timing_shocked.value}).")
        else:
            reasons.append(f"Strategy remains resilient at {rec_baseline.value} ({timing_baseline.value}).")

        plain_language = ' '.join(reasons)

        return ScenarioSimulationOutput(
            scenario_name=scenario_name,
            baseline_freight_usd_mt=round(baseline_freight_usd_mt, 2),
            shocked_freight_usd_mt=round(shocked_freight_usd_mt, 2),
            freight_delta_usd_mt=round(freight_delta_usd_mt, 2),
            freight_delta_pct=round(freight_delta_pct, 1),
            baseline_freight_inr_mt=round(baseline_freight_inr_mt, 2),
            shocked_freight_inr_mt=round(shocked_freight_inr_mt, 2),
            freight_delta_inr_mt=round(freight_delta_inr_mt, 2),
            fuel_cost_impact_usd_mt=round(fuel_impact_usd_mt, 2),
            demurrage_impact_usd_mt=round(demurrage_impact_usd_mt, 2),
            market_tightness_impact_usd_mt=round(market_tightness_impact_usd_mt, 2),
            recommended_charter_type_baseline=rec_baseline,
            recommended_charter_type_shocked=rec_shocked,
            recommended_timing_baseline=timing_baseline,
            recommended_timing_shocked=timing_shocked,
            strategy_shifted=strategy_shifted,
            plain_language_rationale=plain_language
        )
