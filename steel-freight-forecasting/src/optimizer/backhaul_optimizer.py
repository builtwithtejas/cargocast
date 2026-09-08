from typing import List, Dict, Optional, Tuple
from src.schemas.base import BaseModel, Field
from src.schemas.port_models import VesselClass

class BackhaulOption(BaseModel):
    option_id: str
    name: str
    origin_load_port: str
    destination_discharge_port: str
    commodity: str
    nominal_parcel_mt: float
    backhaul_revenue_rate_usd_mt: float
    additional_voyage_days: float
    shared_savings_pct: float # Percentage of backhaul margin credited to steelmaker
    freight_credit_usd_mt: float # Freight discount on coal import
    net_savings_usd: float
    net_savings_inr: float
    co2_emissions_saved_mt: float
    feasibility_notes: str

class BackhaulOptimizationResult(BaseModel):
    primary_import_route: str
    vessel_class: str
    coking_coal_parcel_mt: float
    baseline_direct_freight_usd_mt: float
    baseline_total_freight_usd: float
    optimal_backhaul_option: BackhaulOption
    optimized_net_freight_usd_mt: float
    optimized_total_freight_usd: float
    total_savings_usd: float
    total_savings_inr: float
    effective_discount_pct: float
    all_evaluated_options: List[BackhaulOption]
    executive_summary: str

class BackhaulOptimizer:
    """
    Solves the Idle Scenario & Deadheading problem by evaluating triangulated
    coastal and export backhaul voyages from Indian East Coast ports,
    sharing freight credits to reduce net landed cost of imported coking coal.
    """
    def __init__(self, base_fx_inr_usd: float = 87.50):
        self.fx_inr_usd = base_fx_inr_usd

    def evaluate_backhauls(
        self,
        import_route_id: str,
        discharge_port_id: str,
        vessel_class: VesselClass,
        coking_coal_parcel_mt: float,
        baseline_freight_usd_mt: float
    ) -> BackhaulOptimizationResult:
        baseline_total_freight = baseline_freight_usd_mt * coking_coal_parcel_mt

        options: List[BackhaulOption] = []

        # Option 1: Coastal Iron Ore Pellet Movement (Paradip/Vizag -> Hazira/West Coast)
        # Paradip/Vizag iron ore pellets destined for AM/NS Hazira or JSW Jaigad
        coastal_pellet_rate = 8.80 # USD/MT coastal freight tariff
        coastal_parcel = min(coking_coal_parcel_mt, 70000.0)
        coastal_days = 6.5
        coastal_share = 0.40 # 40% margin credited to inbound charterer
        coastal_credit = (coastal_parcel * coastal_pellet_rate * coastal_share) / coking_coal_parcel_mt
        coastal_savings_usd = coastal_credit * coking_coal_parcel_mt
        coastal_co2 = round((coastal_parcel / 1000.0) * 14.2, 1)

        options.append(BackhaulOption(
            option_id="BACKHAUL_COASTAL_HAZIRA",
            name="Coastal Iron Ore Pellets (Paradip/Vizag -> Hazira)",
            origin_load_port=discharge_port_id,
            destination_discharge_port="IN_HZR (Hazira, Gujarat)",
            commodity="Iron Ore Pellets",
            nominal_parcel_mt=coastal_parcel,
            backhaul_revenue_rate_usd_mt=coastal_pellet_rate,
            additional_voyage_days=coastal_days,
            shared_savings_pct=40.0,
            freight_credit_usd_mt=round(coastal_credit, 2),
            net_savings_usd=round(coastal_savings_usd, 2),
            net_savings_inr=round(coastal_savings_usd * self.fx_inr_usd, 2),
            co2_emissions_saved_mt=coastal_co2,
            feasibility_notes="High frequency trade lane. Enables domestic coastal steel integration (SAIL/RINL to West Coast mills)."
        ))

        # Option 2: Export Iron Ore to Southeast Asia (Dhamra/Paradip -> Vietnam / Malaysia)
        # Vessel loads export fines/pellets en route back towards Australian Pacific waters
        export_rate = 11.20 # USD/MT export freight
        export_parcel = min(coking_coal_parcel_mt, 80000.0)
        export_days = 9.0
        export_share = 0.45 # 45% margin credit
        export_credit = (export_parcel * export_rate * export_share) / coking_coal_parcel_mt
        export_savings_usd = export_credit * coking_coal_parcel_mt
        export_co2 = round((export_parcel / 1000.0) * 22.5, 1)

        options.append(BackhaulOption(
            option_id="BACKHAUL_EXPORT_SE_ASIA",
            name="Iron Ore Export En-Route (Dhamra/Paradip -> Vietnam/Malaysia)",
            origin_load_port=discharge_port_id,
            destination_discharge_port="VN_VUG (Vung Ang / Dung Quat)",
            commodity="Iron Ore Fines / Pellets",
            nominal_parcel_mt=export_parcel,
            backhaul_revenue_rate_usd_mt=export_rate,
            additional_voyage_days=export_days,
            shared_savings_pct=45.0,
            freight_credit_usd_mt=round(export_credit, 2),
            net_savings_usd=round(export_savings_usd, 2),
            net_savings_inr=round(export_savings_usd * self.fx_inr_usd, 2),
            co2_emissions_saved_mt=export_co2,
            feasibility_notes="Triangulated pacific positioning. Drops ballast deadheading distance to Queensland by 42%."
        ))

        # Option 3: Coastal Thermal Coal / Clinker Movement (Paradip -> Tuticorin/Ennore)
        coastal_south_rate = 6.90
        south_parcel = min(coking_coal_parcel_mt, 65000.0)
        south_days = 4.0
        south_share = 0.35
        south_credit = (south_parcel * coastal_south_rate * south_share) / coking_coal_parcel_mt
        south_savings_usd = south_credit * coking_coal_parcel_mt
        south_co2 = round((south_parcel / 1000.0) * 11.0, 1)

        options.append(BackhaulOption(
            option_id="BACKHAUL_COASTAL_SOUTH",
            name="Coastal Raw Material Repositioning (Paradip -> Ennore/Tuticorin)",
            origin_load_port=discharge_port_id,
            destination_discharge_port="IN_ENR (Kamarajar / Ennore)",
            commodity="Thermal Coal / Flux Minerals",
            nominal_parcel_mt=south_parcel,
            backhaul_revenue_rate_usd_mt=coastal_south_rate,
            additional_voyage_days=south_days,
            shared_savings_pct=35.0,
            freight_credit_usd_mt=round(south_credit, 2),
            net_savings_usd=round(south_savings_usd, 2),
            net_savings_inr=round(south_savings_usd * self.fx_inr_usd, 2),
            co2_emissions_saved_mt=south_co2,
            feasibility_notes="Short-haul domestic repositioning with rapid turnaround."
        ))

        # Optimal Backhaul minimizes net freight
        best_option = max(options, key=lambda x: x.freight_credit_usd_mt)
        optimized_net_freight = max(5.0, baseline_freight_usd_mt - best_option.freight_credit_usd_mt)
        optimized_total_freight = optimized_net_freight * coking_coal_parcel_mt
        total_savings = baseline_total_freight - optimized_total_freight
        discount_pct = round((total_savings / baseline_total_freight) * 100.0, 1)

        vc_str = vessel_class.value if hasattr(vessel_class, 'value') else str(vessel_class)
        summary = (
            f"Triangulated backhaul via '{best_option.name}' captures ${best_option.freight_credit_usd_mt:.2f}/MT "
            f"freight credit on imported coking coal. Reduces net landed freight from ${baseline_freight_usd_mt:.2f}/MT "
            f"to ${optimized_net_freight:.2f}/MT ({discount_pct}% net savings = ₹{total_savings * self.fx_inr_usd / 1e7:.2f} Crores per voyage). "
            f"Mitigates {best_option.co2_emissions_saved_mt:,.0f} MT of ballast CO2 emissions."
        )

        return BackhaulOptimizationResult(
            primary_import_route=import_route_id,
            vessel_class=vc_str,
            coking_coal_parcel_mt=coking_coal_parcel_mt,
            baseline_direct_freight_usd_mt=round(baseline_freight_usd_mt, 2),
            baseline_total_freight_usd=round(baseline_total_freight, 2),
            optimal_backhaul_option=best_option,
            optimized_net_freight_usd_mt=round(optimized_net_freight, 2),
            optimized_total_freight_usd=round(optimized_total_freight, 2),
            total_savings_usd=round(total_savings, 2),
            total_savings_inr=round(total_savings * self.fx_inr_usd, 2),
            effective_discount_pct=discount_pct,
            all_evaluated_options=options,
            executive_summary=summary
        )
