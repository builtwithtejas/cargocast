import unittest
from src.decision import CharterTypeSelector, MarketTimingRecommender
from src.schemas.forecast_models import RouteForecast, HorizonForecast, TrendDirection, VolatilityRegime
from src.schemas.decision_models import CharterType, TimingAction, VesselSuitabilityResult
from src.schemas.disruption_models import PortDisruptionStatus, DisruptionSeverity, DisruptionCategory
from src.schemas.port_models import VesselClass

class TestDecisionLogic(unittest.TestCase):
    def setUp(self):
        self.selector = CharterTypeSelector()
        self.timing_rec = MarketTimingRecommender()

        self.mock_suitability = VesselSuitabilityResult(
            vessel_class=VesselClass.PANAMAX,
            is_feasible=True,
            draft_margin_meters=1.5,
            loa_margin_meters=20.0,
            beam_margin_meters=5.0,
            requires_lighterage=False,
            lighterage_cost_usd_mt=0.0,
            deadweight_utilization_pct=95.0,
            daily_discharge_rate_mt=35000.0,
            estimated_port_turnaround_days=4.5,
            total_voyage_freight_usd_mt=20.50
        )

    def test_upward_trend_high_volume_recommends_coa(self):
        forecast = RouteForecast(
            route_id='R_AU_PRT',
            origin_port_id='AU_HPT',
            discharge_port_id='IN_PRT',
            vessel_class='Panamax',
            commodity='Hard Coking Coal',
            current_spot_rate_usd_mt=15.00,
            current_time_charter_usd_day=24000,
            forecast_horizons=[
                HorizonForecast(horizon_days=7, q10=15.2, q50=15.8, q90=16.5, tce_usd_day=24500),
                HorizonForecast(horizon_days=14, q10=15.8, q50=16.5, q90=17.5, tce_usd_day=25500),
                HorizonForecast(horizon_days=30, q10=16.5, q50=17.8, q90=19.2, tce_usd_day=27500),
                HorizonForecast(horizon_days=60, q10=17.0, q50=18.5, q90=20.5, tce_usd_day=28500),
                HorizonForecast(horizon_days=90, q10=17.5, q50=19.5, q90=21.8, tce_usd_day=30000)
            ],
            trend_slope_usd_day=0.05,
            trend_direction=TrendDirection.UPWARD,
            volatility_regime=VolatilityRegime.MODERATE,
            cargo_demand_monthly_mt=500000
        )
        benign_disruption = PortDisruptionStatus(
            port_id='IN_PRT', port_name='Paradip', disruption_score=0.10,
            severity_level=DisruptionSeverity.LOW, dominant_category=DisruptionCategory.OPERATIONAL_NORMAL,
            active_event_count=0, waiting_time_multiplier=1.1, demurrage_risk_premium_usd_mt=0.12, summary='Normal'
        )

        rec = self.selector.evaluate_charter_strategy(forecast, self.mock_suitability, benign_disruption, 150000)
        self.assertEqual(rec.recommended_charter_type, CharterType.COA_CONTRACT_OF_AFFREIGHTMENT)
        self.assertEqual(rec.recommended_timing, TimingAction.ENTER_IMMEDIATE)
        self.assertGreater(rec.potential_savings_vs_spot_pct, 5.0)

    def test_downward_trend_recommends_spot_and_wait(self):
        forecast = RouteForecast(
            route_id='R_US_DHM',
            origin_port_id='US_ORF',
            discharge_port_id='IN_DHM',
            vessel_class='Panamax',
            commodity='Coking Coal',
            current_spot_rate_usd_mt=32.00,
            current_time_charter_usd_day=26000,
            forecast_horizons=[
                HorizonForecast(horizon_days=7, q10=30.5, q50=31.2, q90=32.0, tce_usd_day=25500),
                HorizonForecast(horizon_days=14, q10=29.8, q50=30.5, q90=31.5, tce_usd_day=25000),
                HorizonForecast(horizon_days=30, q10=28.5, q50=29.2, q90=30.5, tce_usd_day=24000),
                HorizonForecast(horizon_days=60, q10=27.5, q50=28.4, q90=29.8, tce_usd_day=23000),
                HorizonForecast(horizon_days=90, q10=27.0, q50=28.0, q90=29.2, tce_usd_day=22500)
            ],
            trend_slope_usd_day=-0.04,
            trend_direction=TrendDirection.DOWNWARD,
            volatility_regime=VolatilityRegime.LOW,
            cargo_demand_monthly_mt=250000
        )
        benign_disruption = PortDisruptionStatus(
            port_id='IN_DHM', port_name='Dhamra', disruption_score=0.08,
            severity_level=DisruptionSeverity.LOW, dominant_category=DisruptionCategory.OPERATIONAL_NORMAL,
            active_event_count=0, waiting_time_multiplier=1.1, demurrage_risk_premium_usd_mt=0.1, summary='Normal'
        )

        rec = self.selector.evaluate_charter_strategy(forecast, self.mock_suitability, benign_disruption, 75000)
        self.assertEqual(rec.recommended_charter_type, CharterType.SPOT_VOYAGE)
        self.assertEqual(rec.recommended_timing, TimingAction.DEFER_AND_WAIT)

    def test_critical_port_disruption_forces_defer(self):
        severe_disruption = PortDisruptionStatus(
            port_id='IN_PRT', port_name='Paradip', disruption_score=0.95,
            severity_level=DisruptionSeverity.CRITICAL, dominant_category=DisruptionCategory.CYCLONE_MONSOON,
            active_event_count=2, waiting_time_multiplier=3.5, demurrage_risk_premium_usd_mt=1.15, summary='Cyclone'
        )
        forecast = RouteForecast(
            route_id='R_AU_PRT', origin_port_id='AU_HPT', discharge_port_id='IN_PRT',
            vessel_class='Panamax', commodity='Coal', current_spot_rate_usd_mt=15.00,
            current_time_charter_usd_day=24000,
            forecast_horizons=[HorizonForecast(horizon_days=30, q10=16.0, q50=17.5, q90=19.0, tce_usd_day=26000)],
            trend_slope_usd_day=0.04, trend_direction=TrendDirection.UPWARD,
            volatility_regime=VolatilityRegime.MODERATE, cargo_demand_monthly_mt=400000
        )
        rec = self.selector.evaluate_charter_strategy(forecast, self.mock_suitability, severe_disruption, 75000)
        self.assertEqual(rec.recommended_timing, TimingAction.DEFER_AND_WAIT)
        self.assertTrue(any('CRITICAL PORT RISK' in d for d in rec.key_drivers))

if __name__ == '__main__':
    unittest.main()
