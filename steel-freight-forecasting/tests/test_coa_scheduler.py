import unittest
from src.decision.coa_scheduler import AnnualCOAScheduler
from src.schemas.port_models import VesselClass

class TestAnnualCOAScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = AnnualCOAScheduler()

    def test_volume_and_tranche_allocation(self):
        plan = self.scheduler.generate_annual_coa_plan(
            plant_name="SAIL Rourkela",
            annual_coking_coal_demand_mt=1200000.0,
            preferred_vessel_class=VesselClass.PANAMAX,
            base_spot_freight_usd_mt=20.50
        )
        self.assertGreaterEqual(plan.total_scheduled_volume_mt, 1200000.0)
        self.assertGreater(plan.total_voyages_count, 10)
        self.assertGreater(plan.total_annual_savings_inr, 0)
        self.assertGreater(plan.overall_savings_pct, 4.0)

    def test_cyclone_season_avoidance(self):
        plan = self.scheduler.generate_annual_coa_plan(
            plant_name="SAIL Rourkela",
            annual_coking_coal_demand_mt=1200000.0,
            preferred_vessel_class=VesselClass.PANAMAX
        )
        # Verify May and October (peak cyclone months) have minimal or zero allocations
        may_tranches = [t for t in plan.tranches if "May" in t.scheduled_month]
        oct_tranches = [t for t in plan.tranches if "October" in t.scheduled_month]
        feb_tranches = [t for t in plan.tranches if "February" in t.scheduled_month]
        self.assertEqual(len(may_tranches), 0)
        self.assertEqual(len(oct_tranches), 0)
        self.assertGreaterEqual(len(feb_tranches), 2)

if __name__ == '__main__':
    unittest.main()
