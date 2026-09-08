from typing import Dict, List, Tuple
from src.schemas.decision_models import TimingAction
from src.schemas.forecast_models import RouteForecast, TrendDirection
from src.schemas.disruption_models import PortDisruptionStatus, DisruptionSeverity

class MarketTimingRecommender:
    """
    Generates actionable buy-now-vs-wait procurement timing recommendations
    with target execution windows and trigger threshold prices.
    """
    def evaluate_timing_window(
        self,
        forecast: RouteForecast,
        disruption: PortDisruptionStatus
    ) -> Tuple[TimingAction, str, Dict[str, float]]:
        current_spot = forecast.current_spot_rate_usd_mt
        f_7d = next((h.q50 for h in forecast.forecast_horizons if h.horizon_days == 7), current_spot)
        f_14d = next((h.q50 for h in forecast.forecast_horizons if h.horizon_days == 14), current_spot)
        f_30d = next((h.q50 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot)
        q10_30d = next((h.q10 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot * 0.95)
        q90_30d = next((h.q90 for h in forecast.forecast_horizons if h.horizon_days == 30), current_spot * 1.15)

        triggers = {
            'target_entry_rate_usd_mt': round(min(current_spot, f_7d), 2),
            'stop_loss_trigger_rate_usd_mt': round(q90_30d * 1.05, 2),
            'expected_dip_rate_usd_mt': round(q10_30d, 2),
            'current_spot_usd_mt': round(current_spot, 2)
        }

        # 1. Critical Disruption Check
        if disruption.severity_level in [DisruptionSeverity.CRITICAL, DisruptionSeverity.SEVERE]:
            action = TimingAction.DEFER_AND_WAIT
            rationale = (
                f"DEFER CHARTERING (Wait 7 to 14 days). Active disruption ({disruption.dominant_category.value}) "
                f"at {disruption.port_name}. Port waiting multiplier is {disruption.waiting_time_multiplier}x. "
                f"Tendering immediately will result in demurrage accrual (~{disruption.demurrage_risk_premium_usd_mt:.2f} $/MT)."
            )
            return action, rationale, triggers

        # 2. Downward Forecast Trend
        if forecast.trend_direction == TrendDirection.DOWNWARD or (f_14d < current_spot * 0.96):
            action = TimingAction.DEFER_AND_WAIT
            rationale = (
                f"WAIT AND WATCH (Window: 14 to 21 days). Market softening detected. "
                f"Point forecast projects rate dipping from ${current_spot:.2f} to ${f_14d:.2f}/MT within 14 days. "
                f"Target entry when rate touches ${triggers['expected_dip_rate_usd_mt']:.2f}/MT."
            )
            return action, rationale, triggers

        # 3. Upward Trend
        if forecast.trend_direction == TrendDirection.UPWARD and (f_14d > current_spot * 1.03):
            action = TimingAction.ENTER_IMMEDIATE
            rationale = (
                f"EXECUTE IMMEDIATELY (Window: 0 to 72 hours). Freight rates in upward breakout (+{forecast.trend_slope_usd_day:+.3f} $/day). "
                f"Forecast indicates rates reaching ${f_14d:.2f}/MT in 14 days. Securing tonnage today locks the lowest market rate."
            )
            return action, rationale, triggers

        # 4. Volatility regime
        if (q90_30d - q10_30d) / f_30d > 0.25:
            action = TimingAction.ACCUMULATE_STAGGERED
            rationale = (
                f"STAGGERED PROCUREMENT (Window: 1 to 2 weeks). Wide confidence interval (${q10_30d:.2f} - ${q90_30d:.2f}/MT). "
                f"Procure 40-50% volume immediately to cover baseline furnace charge, tender balance in 10-14 days."
            )
            return action, rationale, triggers

        # 5. Default
        action = TimingAction.ENTER_IMMEDIATE
        rationale = f"PROCEED WITH PLANNED SCHEDULE. Ambient market conditions stable around ${current_spot:.2f}/MT."
        return action, rationale, triggers
