import unittest

from agni.landmarks import match_landmark


class LandmarkTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{
            "id": "fixture-vons-carmel-valley",
            "name": "Vons Carmel Valley",
            "aliases": ["Vons at Carmel Valley", "Carmel Valley Vons"],
            "lat": 32.91,
            "lon": -117.17,
            "source": "test-fixture",
        }]

    def test_phrase_matches_only_the_coordinates_in_the_cache(self):
        row = match_landmark("behind the Vons, Carmel Valley", self.rows)
        self.assertEqual(row["id"], "fixture-vons-carmel-valley")
        self.assertEqual((row["lat"], row["lon"]), (32.91, -117.17))

    def test_unknown_place_does_not_get_coordinates(self):
        self.assertIsNone(match_landmark("near my house by the smoke", self.rows))

    def test_record_without_coordinates_is_not_a_pin(self):
        rows = [{"name": "Vons Carmel Valley", "aliases": ["Vons"]}]
        self.assertIsNone(match_landmark("Vons Carmel Valley", rows))


if __name__ == "__main__":
    unittest.main()
