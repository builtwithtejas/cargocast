import unittest
from src.nlp import MaritimeDisruptionScorer
from src.schemas.disruption_models import DisruptionCategory, DisruptionSeverity

class TestMaritimeDisruptionScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = MaritimeDisruptionScorer()

    def test_cyclone_alert_scoring(self):
        headline = 'Severe cyclonic storm approaching Paradip port; pilotage suspended'
        raw = 'IMD warns of gale force winds along Odisha coast. All vessel movement halted.'
        ev = self.scorer.score_news_item('TEST_1', headline, raw)
        self.assertEqual(ev.category, DisruptionCategory.CYCLONE_MONSOON)
        self.assertGreaterEqual(ev.severity_score, 0.75)
        self.assertIn('IN_PRT', ev.affected_ports)
        self.assertIn(ev.severity, [DisruptionSeverity.SEVERE, DisruptionSeverity.CRITICAL])

    def test_dock_strike_scoring(self):
        headline = 'Dockworkers union calls indefinite strike at Paradip Port'
        raw = 'Operations ground to a halt as unions protest wage revisions.'
        ev = self.scorer.score_news_item('TEST_2', headline, raw)
        self.assertEqual(ev.category, DisruptionCategory.LABOR_STRIKE)
        self.assertGreaterEqual(ev.severity_score, 0.70)
        self.assertIn('IN_PRT', ev.affected_ports)

    def test_haldia_siltation_and_sandheads_lighterage(self):
        headline = 'Haldia river draft drops to 7.2m; Sandheads lighterage mandated'
        raw = 'Hooghly channel siltation requires two-stage lightering at Sandheads anchorage.'
        ev = self.scorer.score_news_item('TEST_3', headline, raw)
        self.assertEqual(ev.category, DisruptionCategory.PORT_CONGESTION)
        self.assertIn('IN_HLD', ev.affected_ports)
        self.assertIn('IN_SGR_ANCH', ev.affected_ports)

    def test_relief_keyword_normalization(self):
        headline = 'Normal operations resume at Visakhapatnam port; weather cleared'
        raw = 'Discharge rates have returned to normal capacity and berthing queues normalized.'
        ev = self.scorer.score_news_item('TEST_4', headline, raw)
        self.assertEqual(ev.category, DisruptionCategory.OPERATIONAL_NORMAL)
        self.assertLess(ev.severity_score, 0.25)
        self.assertEqual(ev.severity, DisruptionSeverity.LOW)

    def test_feature_vector_generation(self):
        items = [
            {'news_id': 'N1', 'headline': 'Severe cyclone warning for Paradip and Dhamra', 'raw_text': 'Signals hoisted.', 'target_ports': ['IN_PRT', 'IN_DHM'], 'regions': ['East Coast India']},
            {'news_id': 'N2', 'headline': 'Operations normal at Gangavaram', 'raw_text': 'Weather cleared.', 'target_ports': ['IN_GNR'], 'regions': []}
        ]
        report = self.scorer.generate_daily_report(items)
        self.assertIn('feat_disruption_east_coast_composite', report.feature_vector)
        self.assertIn('feat_disruption_paradip', report.feature_vector)
        self.assertIn('feat_cyclone_active_flag', report.feature_vector)
        self.assertEqual(report.feature_vector['feat_cyclone_active_flag'], 1.0)
        self.assertGreater(report.port_statuses['IN_PRT'].disruption_score, report.port_statuses['IN_GNR'].disruption_score)

if __name__ == '__main__':
    unittest.main()
