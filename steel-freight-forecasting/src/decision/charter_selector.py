from typing import List, Optional
from src.schemas.decision_models import (
    CharterType, TimingAction, CharterRecommendation, VesselSuitabilityResult
)
from src.schemas.forecast_models import RouteForecast, TrendDirection, VolatilityRegime
from src.schemas.disruption_models import PortDisruptionStatus, DisruptionSeverity
from src.schemas.port_models import VesselClass

class CharterTypeSelector:
    """
    Determines optimal chartering contract structure (Spot vs Time Charter vs COA)
    based on freight rate trajectory, quantile uncertainty bands, and port disruption severity.
    """
    def evaluate_charter_strategy(
        self,
        forecast: RouteForecast,
        suitability: VesselSuitabilityResult,
        disruption: PortDisruptionStatus,
        cargo_parcel_mt: float,
        fx_inr_usd: float = 87.50
    ) -> CharterRecommendation:
        drivers: List[str] = []
        hedge_rec: Optional[str] = None
        
        current_spot = forecast.current_spot_rate_usd_mt
        # 30-day forecast point prediction
        f_30d = next((h.q50 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot * 1.05)
        # 90-day forecast for longer outlook
        f_90d = next((h.q90 for h in forecast.forecast_horizons if h.horizon_days == 90), current_spot * 1.15)
        q10_30d = next((h.q10 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot * 0.95)
        q90_30d = next((h.q90 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot * 1.15)

        rate_growth_pct = ((f_30d - current_spot) / current_spot) * 100.0
        volatility_spread_pct = ((q90_30d - q10_30d) / f_30d) * 100.0

        # Base freight cost from physical voyage model
        base_freight = suitability.total_voyage_freight_usd_mt

        # Default decision assignments
        rec_charter = CharterType.SPOT_VOYAGE
        rec_timing = TimingAction.ENTER_IMMEDIATE
        confidence = 0.82
        savings_pct = 0.0

        # DECISION LOGIC RULES:
        # Rule 1: Severe Port Disruption (Strike or Cyclone)
        if disruption.severity_level in [DisruptionSeverity.CRITICAL, DisruptionSeverity.SEVERE]:
            rec_charter = CharterType.SPOT_VOYAGE
            rec_timing = TimingAction.DEFER_AND_WAIT
            confidence = 0.88
            drivers.append(
                f"CRITICAL PORT RISK: {disruption.port_name} experiencing {disruption.dominant_category.value} (Score: {disruption.disruption_score:.2f})."
            )
            drivers.append(
                f"Berthing queue multiplier is {disruption.waiting_time_multiplier}x normal. Entering time-charter now would incur idle daily hire without cargo movement."
            )
            drivers.append("Recommendation: Defer market entry 7-10 days until port clearance is restored.")
            savings_pct = round(disruption.demurrage_risk_premium_usd_mt / base_freight * 100.0, 1)

        # Rule 2: Strong Upward Rate Trajectory + High Parcel Volume
        elif forecast.trend_direction == TrendDirection.UPWARD and rate_growth_pct >= 6.0:
            if cargo_parcel_mt >= 120000 or forecast.cargo_demand_monthly_mt >= 350000:
                rec_charter = CharterType.COA_CONTRACT_OF_AFFREIGHTMENT
                rec_timing = TimingAction.ENTER_IMMEDIATE
                confidence = 0.91
                savings_pct = round(min(14.5, rate_growth_pct * 0.75), 1)
                drivers.append(
                    f"RISING FREIGHT REGIME: 30-day forecast indicates +{rate_growth_pct:.1f}% rate escalation (${current_spot:.2f} -> ${f_30d:.2f}/MT)."
                )
                drivers.append(
                    f"Large steel mill demand ({cargo_parcel_mt:,.0f} MT parcel / {forecast.cargo_demand_monthly_mt:,.0f} MT monthly) favors Contract of Affreightment (COA) to lock indexed discounts."
                )
                drivers.append("Locking multiple-voyage contract now protects against forecasted 90-day peak rates.")
                hedge_rec = "Execute FFA (Forward Freight Agreement) hedge on BCI/BPI Cal-26 contracts for remaining uncontracted volume."
            else:
                rec_charter = CharterType.SHORT_TERM_PERIOD
                rec_timing = TimingAction.ENTER_IMMEDIATE
                confidence = 0.85
                savings_pct = round(min(10.0, rate_growth_pct * 0.60), 1)
                drivers.append(
                    f"UPWARD MOMENTUM: Rate trending upwards (+{rate_growth_pct:.1f}% over 30 days). Lock in 3-6 month period time charter."
                )
                drivers.append("Fixing period charter caps exposure to short-term voyage spikes.")

        # Rule 3: Downward Rate Trajectory
        elif forecast.trend_direction == TrendDirection.DOWNWARD or rate_growth_pct <= -4.0:
            rec_charter = CharterType.SPOT_VOYAGE
            rec_timing = TimingAction.DEFER_AND_WAIT
            confidence = 0.87
            potential_drop = abs(rate_growth_pct)
            savings_pct = round(potential_drop * 0.85, 1)
            drivers.append(
                f"BEARISH FREIGHT MARKET: Rates projected to decline by {potential_drop:.1f}% over the next 30 days (${current_spot:.2f} -> ${f_30d:.2f}/MT)."
            )
            drivers.append("Do NOT lock period charters in a declining market. Maintain spot flexibility to capture lower voyage fixtures.")
            drivers.append("Defer procurement tender by 2-3 weeks to capture softening freight levels.")

        # Rule 4: High Volatility Sideways Market
        elif volatility_spread_pct >= 25.0:
            rec_charter = CharterType.SPOT_VOYAGE
            rec_timing = TimingAction.ACCUMULATE_STAGGERED
            confidence = 0.78
            savings_pct = 4.5
            drivers.append(
                f"HIGH VOLATILITY REGIME: 30-day forecast uncertainty band is wide (${q10_30d:.2f} - ${q90_30d:.2f}/MT, spread: {volatility_spread_pct:.1f}%)."
            )
            drivers.append("Recommend staggered chartering: fix 50% requirement now, tender remainder across 2-week intervals to dollar-cost-average.")
            hedge_rec = "Consider buying call options on Baltic dry index to cap extreme upside risk."

        # Rule 5: Stable / Benign Market
        else:
            rec_charter = CharterType.SPOT_VOYAGE
            rec_timing = TimingAction.ENTER_IMMEDIATE
            confidence = 0.84
            savings_pct = 2.0
            drivers.append("STABLE MARKET: Modest rate movement forecasted within narrow quantile bands.")
            drivers.append("Standard spot voyage chartering optimal for immediate parcel requirements.")

        # Executive Reasoning Synthesis
        exec_reasoning = (
            f"Recommended Strategy: {rec_charter.value} ({rec_timing.value}) for {suitability.vessel_class.value}. "
            f"{drivers[0]} Estimated landed freight: ${base_freight:.2f}/MT (₹{base_freight * fx_inr_usd:,.0f}/MT). "
            f"Potential cost savings vs naive spot chartering: ~{savings_pct}%. Confidence: {int(confidence * 100)}%."
        )

        return CharterRecommendation(
            route_id=forecast.route_id,
            origin_port=forecast.origin_port_id,
            discharge_port=forecast.discharge_port_id,
            commodity=forecast.commodity,
            cargo_parcel_size_mt=cargo_parcel_mt,
            recommended_charter_type=rec_charter,
            recommended_timing=rec_timing,
            optimal_vessel_class=suitability.vessel_class,
            confidence_score=confidence,
            current_spot_rate_usd_mt=current_spot,
            forecast_30d_rate_usd_mt=f_30d,
            expected_landed_cost_usd_mt=base_freight,
            expected_landed_cost_inr_mt=round(base_freight * fx_inr_usd, 2),
            potential_savings_vs_spot_pct=savings_pct,
            executive_reasoning=exec_reasoning,
            key_drivers=drivers,
            disruption_severity=disruption.severity_level,
            hedge_recommendation=hedge_rec,
            vessel_options_evaluated=[suitability]
        )
