import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.schemas.port_models import VesselClass
from src.schemas.forecast_models import ForecastFeed, RouteForecast
from src.schemas.disruption_models import DailyDisruptionReport, PortDisruptionStatus
from src.schemas.decision_models import (
    CharterRecommendation, ScenarioShockInput, ScenarioSimulationOutput
)
from src.nlp import MaritimeDisruptionScorer
from src.optimizer import (
    PortRegistry, VesselMatchingOptimizer, TidalDraftCalculator, BackhaulOptimizer,
    TidePhaseResult, BackhaulOptimizationResult
)
from src.decision import (
    CharterTypeSelector, MarketTimingRecommender, ScenarioSimulator,
    AnnualCOAScheduler, CostSavingsBenchmarkEngine,
    AnnualCOAScheduleResult, CostSavingsBenchmarkReport
)

class SteelFreightDecisionPipeline:
    """
    End-to-end integration orchestrator for ML Engineer #2 (NLP & Decision Logic).
    Stitches together disruption intelligence, vessel suitability optimization,
    charter selection, market timing, scenario stress testing, backhaul optimization,
    tidal riverine calculations, COA scheduling, and cost-savings benchmarking.
    """
    def __init__(self, data_dir: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.data_dir = Path(data_dir) if data_dir else (base_dir / 'data')
        
        self.port_registry = PortRegistry(str(self.data_dir / 'port_specifications.json'))
        self.scorer = MaritimeDisruptionScorer()
        self.optimizer = VesselMatchingOptimizer(self.port_registry)
        self.selector = CharterTypeSelector()
        self.timing_recommender = MarketTimingRecommender()
        self.simulator = ScenarioSimulator(self.port_registry)
        self.tidal_calculator = TidalDraftCalculator()
        self.backhaul_optimizer = BackhaulOptimizer(base_fx_inr_usd=87.50)
        self.coa_scheduler = AnnualCOAScheduler(base_fx_inr_usd=87.50)
        self.benchmark_engine = CostSavingsBenchmarkEngine(base_fx_inr_usd=87.50)

        # Load feeds
        with open(self.data_dir / 'news_disruption_corpus.json') as f:
            self.news_corpus = json.load(f)
        with open(self.data_dir / 'mock_forecast_feed.json') as f:
            self.forecast_feed = ForecastFeed(**json.load(f))

    def run_daily_intelligence(self, as_of_date: Optional[str] = None) -> DailyDisruptionReport:
        target_date = as_of_date or self.forecast_feed.as_of_date
        return self.scorer.generate_daily_report(self.news_corpus, as_of_date=target_date)

    def generate_recommendations(
        self,
        cargo_parcel_mt: float = 75000.0,
        route_ids: Optional[List[str]] = None
    ) -> List[CharterRecommendation]:
        disruption_report = self.run_daily_intelligence()
        routes = self.forecast_feed.routes
        if route_ids:
            routes = [r for r in routes if r.route_id in route_ids]

        recommendations: List[CharterRecommendation] = []
        for rf in routes:
            best_vessel_class, all_suitabilities = self.optimizer.optimize_vessel_selection(
                origin_port_id=rf.origin_port_id,
                discharge_port_id=rf.discharge_port_id,
                cargo_parcel_mt=cargo_parcel_mt,
                bunker_price_usd_mt=self.forecast_feed.base_bunker_vlsfo_usd_mt
            )

            chosen_suitability = next(
                (s for s in all_suitabilities if s.vessel_class == best_vessel_class),
                all_suitabilities[0]
            )

            disruption_status = disruption_report.port_statuses.get(
                rf.discharge_port_id,
                PortDisruptionStatus(
                    port_id=rf.discharge_port_id,
                    port_name=rf.discharge_port_id,
                    disruption_score=0.08,
                    severity_level='LOW',
                    dominant_category='OPERATIONAL_NORMAL',
                    active_event_count=0,
                    waiting_time_multiplier=1.2,
                    demurrage_risk_premium_usd_mt=0.1,
                    summary='Normal traffic'
                )
            )

            rec = self.selector.evaluate_charter_strategy(
                forecast=rf,
                suitability=chosen_suitability,
                disruption=disruption_status,
                cargo_parcel_mt=cargo_parcel_mt,
                fx_inr_usd=self.forecast_feed.base_inr_usd_fx_rate
            )
            rec.vessel_options_evaluated = all_suitabilities
            recommendations.append(rec)

        return recommendations

    def run_scenario(
        self,
        scenario_name: str,
        shocks: ScenarioShockInput,
        route_id: str = 'ROUTE_AU_PRT_CAPE',
        vessel_class: Optional[VesselClass] = None,
        cargo_parcel_mt: float = 75000.0
    ) -> ScenarioSimulationOutput:
        rf = next((r for r in self.forecast_feed.routes if r.route_id == route_id), self.forecast_feed.routes[0])
        disruption_report = self.run_daily_intelligence()
        disruption_status = disruption_report.port_statuses.get(rf.discharge_port_id)
        target_vessel = vessel_class or VesselClass(rf.vessel_class)

        return self.simulator.simulate(
            scenario_name=scenario_name,
            shocks=shocks,
            forecast=rf,
            vessel_class=target_vessel,
            cargo_parcel_mt=cargo_parcel_mt,
            disruption=disruption_status,
            base_bunker_usd_mt=self.forecast_feed.base_bunker_vlsfo_usd_mt,
            base_fx_inr_usd=self.forecast_feed.base_inr_usd_fx_rate
        )

    def evaluate_backhaul_opportunities(
        self,
        route_id: str = 'ROUTE_AU_PRT_CAPE',
        discharge_port_id: str = 'IN_PRT',
        vessel_class: VesselClass = VesselClass.PANAMAX,
        cargo_parcel_mt: float = 75000.0,
        baseline_freight_usd_mt: float = 20.43
    ) -> BackhaulOptimizationResult:
        return self.backhaul_optimizer.evaluate_backhauls(
            import_route_id=route_id,
            discharge_port_id=discharge_port_id,
            vessel_class=vessel_class,
            coking_coal_parcel_mt=cargo_parcel_mt,
            baseline_freight_usd_mt=baseline_freight_usd_mt
        )

    def calculate_haldia_tidal_draft(
        self,
        arrival_date_str: str = '2026-09-02',
        vessel_class: VesselClass = VesselClass.SUPRAMAX,
        cargo_parcel_mt: float = 55000.0
    ) -> TidePhaseResult:
        return self.tidal_calculator.evaluate_haldia_arrival_draft(
            arrival_date_str=arrival_date_str,
            vessel_class=vessel_class,
            cargo_parcel_mt=cargo_parcel_mt
        )

    def generate_annual_coa_plan(
        self,
        plant_name: str = "SAIL Rourkela & Bokaro Steel Plants",
        annual_coking_coal_demand_mt: float = 1200000.0,
        preferred_vessel_class: VesselClass = VesselClass.PANAMAX
    ) -> AnnualCOAScheduleResult:
        return self.coa_scheduler.generate_annual_coa_plan(
            plant_name=plant_name,
            annual_coking_coal_demand_mt=annual_coking_coal_demand_mt,
            preferred_vessel_class=preferred_vessel_class
        )

    def run_cost_savings_benchmark(
        self,
        annual_volume_mt: float = 1200000.0
    ) -> CostSavingsBenchmarkReport:
        return self.benchmark_engine.run_12_month_backtest(
            annual_volume_mt=annual_volume_mt
        )

    def export_dashboard_payload(self) -> Dict[str, Any]:
        """
        Builds the comprehensive, ready-to-consume JSON contract payload for
        Engineer #5 (Backend Dev) and Engineer #6 (Dashboard Dev).
        """
        disruption = self.run_daily_intelligence()
        recs = self.generate_recommendations()

        fuel_shock = self.run_scenario(
            'Bunker Fuel Spike (+20%)',
            ScenarioShockInput(fuel_price_pct_shock=20.0)
        )
        cyclone_shock = self.run_scenario(
            'Severe Cyclone Delay (+4 days)',
            ScenarioShockInput(weather_cyclone_delay_days=4.0, port_congestion_delay_days=2.0)
        )
        demand_shock = self.run_scenario(
            'Steel Plant Demand Surge (+25%)',
            ScenarioShockInput(cargo_demand_pct_shock=25.0)
        )

        backhaul = self.evaluate_backhaul_opportunities()
        haldia_tide = self.calculate_haldia_tidal_draft()
        coa_schedule = self.generate_annual_coa_plan()
        benchmark_12m = self.run_cost_savings_benchmark()

        return {
            'as_of_date': self.forecast_feed.as_of_date,
            'market_benchmarks': {
                'baltic_dry_index': self.forecast_feed.base_bdi,
                'baltic_capesize_index': self.forecast_feed.base_bci,
                'baltic_panamax_index': self.forecast_feed.base_bpi,
                'bunker_vlsfo_usd_mt': self.forecast_feed.base_bunker_vlsfo_usd_mt,
                'fx_inr_usd': self.forecast_feed.base_inr_usd_fx_rate
            },
            'disruption_intelligence': disruption.model_dump(),
            'charter_recommendations': [r.model_dump() for r in recs],
            'precomputed_scenarios': [
                fuel_shock.model_dump(),
                cyclone_shock.model_dump(),
                demand_shock.model_dump()
            ],
            'backhaul_optimization': backhaul.model_dump(),
            'haldia_tidal_analysis': haldia_tide.model_dump(),
            'annual_coa_schedule_preview': {
                'total_scheduled_volume_mt': coa_schedule.total_scheduled_volume_mt,
                'total_voyages_count': coa_schedule.total_voyages_count,
                'total_annual_savings_inr_crores': coa_schedule.total_annual_savings_inr / 10000000.0,
                'overall_savings_pct': coa_schedule.overall_savings_pct,
                'sample_tranches': [t.model_dump() for t in coa_schedule.tranches[:4]]
            },
            'cost_savings_benchmark_12m': {
                'annual_cargo_volume_mt': benchmark_12m.annual_cargo_volume_mt,
                'naive_spend_crores': benchmark_12m.naive_strategy_total_spend_inr / 10000000.0,
                'model_spend_crores': benchmark_12m.model_strategy_total_spend_inr / 10000000.0,
                'net_savings_crores': benchmark_12m.net_annual_savings_inr_crores,
                'savings_pct': benchmark_12m.overall_cost_reduction_pct,
                'demurrage_days_avoided': benchmark_12m.total_demurrage_days_avoided,
                'verdict': benchmark_12m.executive_verdict
            },
            'feature_vector_for_feature_engineer': disruption.feature_vector
        }
