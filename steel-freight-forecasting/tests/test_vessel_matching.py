import unittest
from src.optimizer import VesselMatchingOptimizer, PortRegistry
from src.schemas.port_models import VesselClass

class TestVesselMatching(unittest.TestCase):
    def setUp(self):
        self.opt = VesselMatchingOptimizer()

    def test_capesize_deepwater_suitability(self):
        # Gangavaram and Vizag Outer have 18m+ drafts, capable of handling Capesize directly
        res_gnr = self.opt.evaluate_vessel_class('AU_HPT', 'IN_GNR', VesselClass.CAPESIZE, 150000)
        self.assertTrue(res_gnr.is_feasible)
        self.assertFalse(res_gnr.requires_lighterage)
        self.assertGreater(res_gnr.draft_margin_meters, 0.5)

    def test_haldia_severe_draft_and_loa_constraints(self):
        # Haldia max draft is 8.5m, LOA 230m. Capesize draft is 18.2m, LOA 292m.
        res_hld_cape = self.opt.evaluate_vessel_class('ID_TBN', 'IN_HLD', VesselClass.CAPESIZE, 75000)
        self.assertFalse(res_hld_cape.is_feasible)
        self.assertTrue(any('LOA' in w for w in res_hld_cape.warnings))

        # Handysize at Haldia is feasible
        res_hld_handy = self.opt.evaluate_vessel_class('ID_TBN', 'IN_HLD', VesselClass.HANDYSIZE, 35000)
        self.assertTrue(res_hld_handy.is_feasible)

    def test_lighterage_cost_calculation(self):
        # Supramax laden draft is 12.8m, Haldia is 8.5m. Haldia allows lighterage via Sandheads
        res_hld_supra = self.opt.evaluate_vessel_class('ID_TBN', 'IN_HLD', VesselClass.SUPRAMAX, 55000)
        self.assertTrue(res_hld_supra.requires_lighterage)
        self.assertGreater(res_hld_supra.lighterage_cost_usd_mt, 0.0)

    def test_multi_voyage_parcellation_economics(self):
        # 150,000 MT carried by Handysize requires multiple voyages and is much more expensive per MT than Panamax
        res_handy = self.opt.evaluate_vessel_class('AU_HPT', 'IN_GNR', VesselClass.HANDYSIZE, 150000)
        res_panamax = self.opt.evaluate_vessel_class('AU_HPT', 'IN_GNR', VesselClass.PANAMAX, 150000)
        self.assertGreater(res_handy.total_voyage_freight_usd_mt, res_panamax.total_voyage_freight_usd_mt)

if __name__ == '__main__':
    unittest.main()
