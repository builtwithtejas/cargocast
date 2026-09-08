import unittest
from src.optimizer.backhaul_optimizer import BackhaulOptimizer
from src.schemas.port_models import VesselClass

class TestBackhaulOptimizer(unittest.TestCase):
    def setUp(self):
        self.opt = BackhaulOptimizer()

    def test_backhaul_freight_discount_calculation(self):
        res = self.opt.evaluate_backhauls(
            import_route_id="ROUTE_AU_PRT_CAPE",
            discharge_port_id="IN_PRT",
            vessel_class=VesselClass.PANAMAX,
            coking_coal_parcel_mt=75000.0,
            baseline_freight_usd_mt=20.43
        )
        self.assertGreater(len(res.all_evaluated_options), 2)
        self.assertLess(res.optimized_net_freight_usd_mt, res.baseline_direct_freight_usd_mt)
        self.assertGreater(res.total_savings_usd, 0)
        self.assertGreater(res.total_savings_inr, 0)
        self.assertGreater(res.effective_discount_pct, 5.0)

    def test_co2_savings_reported(self):
        res = self.opt.evaluate_backhauls(
            import_route_id="ROUTE_AU_PRT_CAPE",
            discharge_port_id="IN_PRT",
            vessel_class=VesselClass.PANAMAX,
            coking_coal_parcel_mt=75000.0,
            baseline_freight_usd_mt=20.43
        )
        self.assertGreater(res.optimal_backhaul_option.co2_emissions_saved_mt, 0)

if __name__ == '__main__':
    unittest.main()
