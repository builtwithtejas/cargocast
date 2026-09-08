import unittest
from src.decision.cost_savings_benchmark import CostSavingsBenchmarkEngine

class TestCostSavingsBenchmark(unittest.TestCase):
    def setUp(self):
        self.engine = CostSavingsBenchmarkEngine()

    def test_12_month_backtest_savings(self):
        res = self.engine.run_12_month_backtest(annual_volume_mt=1200000.0)
        self.assertEqual(len(res.monthly_breakdown), 12)
        self.assertLess(res.model_strategy_total_spend_usd, res.naive_strategy_total_spend_usd)
        self.assertGreater(res.net_annual_savings_inr_crores, 5.0) # at least 5+ Crores
        self.assertGreater(res.total_demurrage_days_avoided, 10.0)
        self.assertIn("verified net savings", res.executive_verdict)

if __name__ == '__main__':
    unittest.main()
