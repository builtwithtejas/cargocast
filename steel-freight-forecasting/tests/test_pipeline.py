import unittest
from src.pipeline import SteelFreightDecisionPipeline

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = SteelFreightDecisionPipeline()

    def test_daily_intelligence_report(self):
        report = self.pipeline.run_daily_intelligence()
        self.assertIsNotNone(report.composite_east_coast_score)
        self.assertIn('IN_PRT', report.port_statuses)
        self.assertIn('feat_disruption_east_coast_composite', report.feature_vector)

    def test_recommendation_generation(self):
        recs = self.pipeline.generate_recommendations(cargo_parcel_mt=75000)
        self.assertGreater(len(recs), 0)
        for r in recs:
            self.assertIsNotNone(r.recommended_charter_type)
            self.assertIsNotNone(r.recommended_timing)
            self.assertGreater(r.expected_landed_cost_usd_mt, 0)
            self.assertGreater(r.expected_landed_cost_inr_mt, 0)

    def test_export_dashboard_payload(self):
        payload = self.pipeline.export_dashboard_payload()
        self.assertIn('market_benchmarks', payload)
        self.assertIn('disruption_intelligence', payload)
        self.assertIn('charter_recommendations', payload)
        self.assertIn('precomputed_scenarios', payload)
        self.assertIn('feature_vector_for_feature_engineer', payload)

if __name__ == '__main__':
    unittest.main()
