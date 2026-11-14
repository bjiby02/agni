import unittest

from agni import routing


class RoutingTests(unittest.TestCase):
    def test_road_closure_moves_the_recommendation_to_an_unblocked_unit(self):
        units = [
            {"id": "near", "callsign": "Engine Near", "lat": 32.0, "lon": -117.02, "status": "available"},
            {"id": "clear", "callsign": "Engine Clear", "lat": 32.02, "lon": -117.00, "status": "available"},
        ]
        closure = {"id": "closure-1", "title": "Fixture closure", "geometry": {
            "type": "LineString", "coordinates": [[-117.01, 31.99], [-117.01, 32.01]],
        }}
        routes = routing.route_options((32.0, -117.0), units, [closure])
        self.assertEqual(routes[0]["unit_id"], "clear")
        self.assertFalse(routes[0]["path_blocked"])
        self.assertTrue(routes[1]["path_blocked"])
        self.assertEqual(routes[1]["route_kind"], "estimate")

    def test_downwind_shelter_is_refused_with_a_reason(self):
        shelters = [
            {"name": "Torrey Pines HS", "lat": 32.0, "lon": -116.98},
            {"name": "RIMAC", "lat": 32.0, "lon": -117.03},
        ]
        result = routing.choose_shelter((32.0, -117.0), shelters, wind_to_deg=90)
        self.assertEqual(result["shelter"]["name"], "RIMAC")
        self.assertEqual(result["refused"], [{"name": "Torrey Pines HS", "reason": "downwind of the estimate"}])


if __name__ == "__main__":
    unittest.main()
