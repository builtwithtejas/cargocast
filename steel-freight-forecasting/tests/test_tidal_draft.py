import unittest
from src.optimizer.tidal_draft import TidalDraftCalculator
from src.schemas.port_models import VesselClass

class TestTidalDraft(unittest.TestCase):
    def setUp(self):
        self.calc = TidalDraftCalculator()

    def test_haldia_tidal_calculation(self):
        res = self.calc.evaluate_haldia_arrival_draft("2026-09-02", VesselClass.SUPRAMAX, 55000)
        self.assertIsNotNone(res.tide_phase)
        self.assertGreater(res.effective_max_draft_meters, 6.5)
        self.assertLess(res.effective_max_draft_meters, 9.5)

    def test_lighterage_triggered_for_deep_vessel(self):
        # 12.8m draft Supramax at Haldia (8.5m max) must trigger lighterage
        res = self.calc.evaluate_haldia_arrival_draft("2026-09-02", VesselClass.SUPRAMAX, 55000, vessel_draft_m=12.8)
        self.assertTrue(res.requires_lighterage)
        self.assertGreater(res.lighterage_tonnage_mt, 0)
        self.assertGreater(res.lighterage_surcharge_usd_mt, 0)
        self.assertIn("Sandheads", res.operational_advice)

    def test_shallow_barge_no_lighterage(self):
        # 6.0m draft barge does not need lighterage
        res = self.calc.evaluate_haldia_arrival_draft("2026-09-02", VesselClass.HANDYSIZE, 20000, vessel_draft_m=6.0)
        self.assertFalse(res.requires_lighterage)
        self.assertEqual(res.lighterage_tonnage_mt, 0)

if __name__ == '__main__':
    unittest.main()
