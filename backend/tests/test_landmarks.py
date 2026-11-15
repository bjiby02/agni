import unittest
from unittest import mock

from agni.landmarks import cached_landmarks, geocode_place, locate, match_landmark


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
        self.assertEqual(row["location_src"], "landmark")

    def test_unknown_place_does_not_get_coordinates(self):
        self.assertIsNone(match_landmark("near my house by the smoke", self.rows))

    def test_record_without_coordinates_is_not_a_pin(self):
        rows = [{"name": "Vons Carmel Valley", "aliases": ["Vons"]}]
        self.assertIsNone(match_landmark("Vons Carmel Valley", rows))

    def test_seed_includes_jacobs_and_ucsd_aliases(self):
        rows = cached_landmarks()
        self.assertGreaterEqual(len(rows), 60)
        jacobs = match_landmark("Jacobs Call Center", rows)
        self.assertIsNotNone(jacobs)
        self.assertEqual(jacobs["id"], "jacobs-school")
        self.assertTrue(32.87 < jacobs["lat"] < 32.89)
        geisel = match_landmark("near Geisel Library", rows)
        self.assertIsNotNone(geisel)
        self.assertEqual(geisel["id"], "geisel")
        rimac = match_landmark("RIMAC", rows)
        self.assertIsNotNone(rimac)

    def test_locate_uses_cache_before_geocode(self):
        with mock.patch("agni.landmarks.geocode_place") as geo_fn:
            hit = locate("smoke behind the Vons Carmel Valley", self.rows)
            self.assertEqual(hit["id"], "fixture-vons-carmel-valley")
            geo_fn.assert_not_called()

    def test_locate_falls_back_to_geocode_on_cache_miss(self):
        fake = {"name": "Some Place", "lat": 32.88, "lon": -117.23, "location_src": "geocode"}
        with mock.patch("agni.landmarks.geocode_place", return_value=fake) as geo_fn:
            hit = locate("weird unnamed trailhead near mesa", self.rows)
            self.assertEqual(hit["location_src"], "geocode")
            geo_fn.assert_called_once()

    def test_geocode_skipped_in_mock_mode(self):
        with mock.patch("agni.landmarks.settings") as cfg:
            cfg.mock = True
            self.assertIsNone(geocode_place("Torrey Pines High School"))


if __name__ == "__main__":
    unittest.main()
