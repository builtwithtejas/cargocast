import unittest
from src.decision import ScenarioSimulator
from src.schemas.decision_models import ScenarioShockInput
from src.schemas.forecast_models import RouteForecast, HorizonForecast, TrendDirection, VolatilityRegime
from src.schemas.disruption_models import PortDisruptionStatus, DisruptionSeverity, DisruptionCategory
from src.schemas.port_models import VesselClass

class TestScenarioSimulator(unittest.TestCase):
    def setUp(self):
        self.simulator = ScenarioSimulator()
        self.forecast = RouteForecast(
            route_id='ROUTE_AU_PRT_CAPE',
            origin_port_id='AU_HPT',
            discharge_port_id='IN_PRT',
            vessel_class='Panamax',
            commodity='Hard Coking Coal',
            current_spot_rate_usd_mt=15.40,
            current_time_charter_usd_day=24500,
            forecast_horizons=[
                HorizonForecast(horizon_days=30, q10=16.0, q50=17.35, q90=19.1, tce_usd_day=27800)
            ],
            trend_slope_usd_day=0.044,
            trend_direction=TrendDirection.UPWARD,
            volatility_regime=VolatilityRegime.MODERATE,
            cargo_demand_monthly_mt=650000
        )
        self.disruption = PortDisruptionStatus(
            port_id='IN_PRT', port_name='Paradip', disruption_score=0.10,
            severity_level=DisruptionSeverity.LOW, dominant_category=DisruptionCategory.OPERATIONAL_NORMAL,
            active_event_count=0, waiting_time_multiplier=1.2, demurrage_risk_premium_usd_mt=0.15, summary='Normal'
        )

    def test_bunker_fuel_shock_calculation(self):
        shock = ScenarioShockInput(fuel_price_pct_shock=25.0)
        res = self.simulator.simulate('Fuel +25%', shock, self.forecast, VesselClass.PANAMAX, 75000, self.disruption)
        self.assertGreater(res.fuel_cost_impact_usd_mt, 0.0)
        self.assertAlmostEqual(res.freight_delta_usd_mt, res.fuel_cost_impact_usd_mt, places=1)
        self.assertIn('Fuel shock', res.plain_language_rationale)

    def test_cyclone_delay_shock_calculation(self):
        shock = ScenarioShockInput(weather_cyclone_delay_days=5.0)
        res = self.simulator.simulate('Cyclone Delay', shock, self.forecast, VesselClass.PANAMAX, 75000, self.disruption)
        self.assertGreater(res.demurrage_impact_usd_mt, 0.5)
        self.assertIn('5.0 days operational delay', res.plain_language_rationale)

    def test_strategy_shift_under_extreme_weather(self):
        shock = ScenarioShockInput(weather_cyclone_delay_days=4.0, port_congestion_delay_days=3.0)
        res = self.simulator.simulate('Severe Port Closure', shock, self.forecast, VesselClass.PANAMAX, 75000, self.disruption)
        self.assertTrue(res.strategy_shifted)
        self.assertEqual(res.recommended_timing_shocked.value, 'DEFER_AND_WAIT')

if __name__ == '__main__':
    unittest.main()
