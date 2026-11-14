import unittest

from agni.domain import IncidentStatus, demo_service


class DispatchServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = demo_service()
        self.incident_id = next(iter(self.service.incidents))

    def test_hazard_penalty_changes_recommendation(self):
        ranked = self.service.rank_units(self.service.incidents[self.incident_id])
        self.assertFalse(ranked[0]["path_blocked"])
        self.assertEqual(ranked[0]["unit"].callsign, "Engine 17")

    def test_vision_escalates_critical_signals(self):
        incident = self.service.record_vision(self.incident_id, "heavy", True, True)
        self.assertEqual(incident.triage_level, 1)

    def test_override_has_highest_priority_state(self):
        incident = self.service.enable_override(self.incident_id, "Confirm wheelchair evacuation needs")
        self.assertEqual(incident.status, IncidentStatus.HUMAN_OVERRIDE)

