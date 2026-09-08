import math
from typing import List, Dict, Tuple, Optional
from src.schemas.port_models import VesselClass, PortInfrastructure, VesselSpecification
from src.schemas.decision_models import VesselSuitabilityResult
from .port_registry import PortRegistry, VESSEL_SPECS

class VesselMatchingOptimizer:
    """
    Evaluates physical suitability of vessel classes for origin-discharge pairs,
    accounting for draft, LOA, beam, lighterage surcharges, part-loading,
    and multi-voyage parcellation.
    """
    def __init__(self, port_registry: Optional[PortRegistry] = None):
        self.registry = port_registry or PortRegistry()

    def evaluate_vessel_class(
        self,
        origin_port_id: str,
        discharge_port_id: str,
        vessel_class: VesselClass,
        cargo_parcel_mt: float,
        bunker_price_usd_mt: float = 635.0,
        fx_inr_usd: float = 87.50
    ) -> VesselSuitabilityResult:
        origin = self.registry.get_port(origin_port_id)
        discharge = self.registry.get_port(discharge_port_id)
        v_spec = self.registry.get_vessel_spec(vessel_class)

        if not origin or not discharge:
            raise ValueError(f"Invalid port ID: {origin_port_id} or {discharge_port_id}")

        warnings = []
        is_feasible = True

        # 1. Draft Analysis at Discharge & Origin Ports
        max_allowed_draft = min(discharge.max_draft_meters, origin.max_draft_meters)
        effective_draft_margin = max_allowed_draft - v_spec.laden_draft_meters

        requires_lighterage = False
        lighterage_cost_usd_mt = 0.0

        # Physical LOA & Beam limits (Strict physical constraints)
        loa_margin = min(discharge.max_loa_meters - v_spec.length_overall_loa_meters,
                         origin.max_loa_meters - v_spec.length_overall_loa_meters)
        beam_margin = min(discharge.max_beam_meters - v_spec.beam_meters,
                          origin.max_beam_meters - v_spec.beam_meters)

        if loa_margin < -5.0: # allow 5m navigational tolerance
            is_feasible = False
            warnings.append(f"INFEASIBLE: Vessel LOA ({v_spec.length_overall_loa_meters}m) exceeds permissible harbor lock/berth LOA ({discharge.max_loa_meters}m).")
        if beam_margin < -2.0:
            is_feasible = False
            warnings.append(f"INFEASIBLE: Vessel Beam ({v_spec.beam_meters}m) exceeds berth pocket channel limit ({discharge.max_beam_meters}m).")

        # Draft handling
        if effective_draft_margin < 0:
            excess_draft_m = abs(effective_draft_margin)
            # Check if port has lighterage facility (e.g. Haldia via Sandheads, or Vizag)
            if discharge.requires_lighterage_for_cape or discharge.lighterage_anchorage_id:
                requires_lighterage = True
                excess_draft_cm = excess_draft_m * 100.0
                tpc = (v_spec.nominal_cargo_intake_mt / 1000.0) * 0.70 # approx TPC
                lighter_tons = min(cargo_parcel_mt * 0.50, excess_draft_cm * tpc)
                unit_lighterage_rate = 5.75 # USD/MT standard lighterage
                lighterage_cost_usd_mt = round((lighter_tons * unit_lighterage_rate) / cargo_parcel_mt, 2)
                warnings.append(
                    f"Draft restriction: {v_spec.laden_draft_meters:.1f}m draft exceeds {max_allowed_draft:.1f}m. "
                    f"Requires lightering {lighter_tons:,.0f} MT at Sandheads/anchorage. Lighterage surcharge: ${lighterage_cost_usd_mt:.2f}/MT."
                )
            elif excess_draft_m <= 1.5:
                # Part-loading / short-loading without lighterage (e.g. Paradip Cape up to 17.1m)
                warnings.append(
                    f"Part-loading required: Vessel must be short-loaded by {excess_draft_m:.1f}m to meet {max_allowed_draft:.1f}m draft limit."
                )
            else:
                is_feasible = False
                warnings.append(
                    f"PHYSICALLY INFEASIBLE: Vessel laden draft {v_spec.laden_draft_meters:.1f}m exceeds port draft {max_allowed_draft:.1f}m by {excess_draft_m:.1f}m and no lighterage possible."
                )

        # 2. Permissible vessel types check
        if vessel_class not in discharge.permissible_vessel_types and not requires_lighterage:
            is_feasible = False
            warnings.append(f"Vessel class {vessel_class.value} not certified for direct berthing at {discharge.port_name}.")

        # 3. Parcellation & Number of Voyages
        max_intake_per_voyage = v_spec.nominal_cargo_intake_mt
        # If draft-constrained part-loading, reduce max intake proportionally
        if effective_draft_margin < 0 and not requires_lighterage:
            draft_reduction_ratio = max(0.60, max_allowed_draft / v_spec.laden_draft_meters)
            max_intake_per_voyage = v_spec.nominal_cargo_intake_mt * draft_reduction_ratio

        voyages_needed = math.ceil(cargo_parcel_mt / max_intake_per_voyage)
        dwt_utilization = min(100.0, round((cargo_parcel_mt / (voyages_needed * max_intake_per_voyage)) * 100.0, 1))

        if voyages_needed > 1:
            warnings.append(f"Multi-voyage required: Parcel size of {cargo_parcel_mt:,.0f} MT requires {voyages_needed} separate {vessel_class.value} shipments.")

        # 4. Voyage Economics per Shipment
        distance_nm = origin.sailing_distance_nm or 4500
        speed_knots = 12.5
        sea_days_one_way = distance_nm / (speed_knots * 24.0)
        round_trip_sea_days = sea_days_one_way * 2.0

        load_rate = origin.daily_loading_rate_mt or 45000
        discharge_rate = discharge.daily_discharge_rate_mt or 30000
        parcel_per_voyage = cargo_parcel_mt / voyages_needed

        port_days_load = parcel_per_voyage / load_rate
        port_days_discharge = parcel_per_voyage / discharge_rate
        waiting_days = discharge.typical_waiting_time_days
        total_port_days_per_voyage = port_days_load + port_days_discharge + waiting_days
        total_voyage_days_per_trip = round_trip_sea_days + total_port_days_per_voyage

        hire_cost = total_voyage_days_per_trip * v_spec.standard_charter_hire_baseline_usd_day
        sea_fuel = round_trip_sea_days * v_spec.fuel_consumption_sea_mt_day
        port_fuel = total_port_days_per_voyage * v_spec.fuel_consumption_port_mt_day
        bunker_cost = (sea_fuel + port_fuel) * bunker_price_usd_mt

        port_charges = 180000.0 if vessel_class == VesselClass.CAPESIZE else (
            130000.0 if vessel_class == VesselClass.PANAMAX else (
                95000.0 if vessel_class == VesselClass.SUPRAMAX else 70000.0
            )
        )

        cost_per_voyage = hire_cost + bunker_cost + port_charges
        total_freight_all_voyages = (cost_per_voyage * voyages_needed) + (lighterage_cost_usd_mt * cargo_parcel_mt)
        total_freight_usd_mt = total_freight_all_voyages / cargo_parcel_mt

        return VesselSuitabilityResult(
            vessel_class=vessel_class,
            is_feasible=is_feasible,
            draft_margin_meters=round(effective_draft_margin, 2),
            loa_margin_meters=round(loa_margin, 2),
            beam_margin_meters=round(beam_margin, 2),
            requires_lighterage=requires_lighterage,
            lighterage_cost_usd_mt=lighterage_cost_usd_mt,
            deadweight_utilization_pct=dwt_utilization,
            daily_discharge_rate_mt=discharge_rate,
            estimated_port_turnaround_days=round(port_days_discharge + waiting_days, 1),
            total_voyage_freight_usd_mt=round(total_freight_usd_mt, 2),
            warnings=warnings
        )

    def optimize_vessel_selection(
        self,
        origin_port_id: str,
        discharge_port_id: str,
        cargo_parcel_mt: float,
        bunker_price_usd_mt: float = 635.0
    ) -> Tuple[VesselClass, List[VesselSuitabilityResult]]:
        results = []
        for vc in [VesselClass.HANDYSIZE, VesselClass.SUPRAMAX, VesselClass.PANAMAX, VesselClass.CAPESIZE]:
            res = self.evaluate_vessel_class(
                origin_port_id=origin_port_id,
                discharge_port_id=discharge_port_id,
                vessel_class=vc,
                cargo_parcel_mt=cargo_parcel_mt,
                bunker_price_usd_mt=bunker_price_usd_mt
            )
            results.append(res)

        feasible_results = [r for r in results if r.is_feasible]
        if not feasible_results:
            return VesselClass.HANDYSIZE, results

        # Best candidate minimizes total landed freight USD/MT while maintaining feasibility
        best_candidate = min(feasible_results, key=lambda x: x.total_voyage_freight_usd_mt)
        return best_candidate.vessel_class, results
