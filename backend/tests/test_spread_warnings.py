import unittest

from agni import spread, warnings


class SpreadAndWarningTests(unittest.TestCase):
    def test_northwest_wind_moves_the_estimate_southeast(self):
        origin = (32.90, -117.20)
        ring = spread.estimate_ring(*origin, wind_to_deg=135, minutes=30)
        lat, lon = spread.centroid(ring)
        self.assertLess(lat, origin[0])
        self.assertGreater(lon, origin[1])
        self.assertEqual(ring["properties"]["label"], "30-min estimate")
        self.assertEqual(ring["properties"]["grid_cell_m"], 100)

    def test_warning_selection_requires_opt_in_and_ring_membership(self):
        ring = spread.estimate_ring(32.90, -117.20, wind_to_deg=135, minutes=30)
        contacts = [
            {"id": "inside", "phone": "mock:inside", "lat": 32.898, "lon": -117.198, "opted_in": True},
            {"id": "outside", "phone": "mock:outside", "lat": 32.96, "lon": -117.27, "opted_in": True},
            {"id": "not-opted-in", "phone": "mock:no", "lat": 32.898, "lon": -117.198, "opted_in": False},
        ]
        selected = warnings.targeted_contacts(ring, contacts)
        self.assertEqual([row["id"] for row in selected], ["inside"])


if __name__ == "__main__":
    unittest.main()
