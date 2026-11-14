import unittest
from unittest.mock import patch

from agni import vision


class VisionTests(unittest.TestCase):
    def tearDown(self):
        vision.clear_cache()

    def test_gemini_box_coordinates_are_normalized_once(self):
        self.assertEqual(vision.normalize_box([100, 200, 700, 800]), [0.2, 0.1, 0.8, 0.7])
        self.assertIsNone(vision.normalize_box([100, 200, 100, 800]))

    def test_same_frame_uses_cache_after_the_first_result(self):
        sample = {"label": "smoke", "box_2d": [100, 200, 700, 800], "flames_visible": False,
                  "reason": "Smoke is visible", "recommended_level": 2, "status": "fixture"}
        with patch("agni.vision._assess_uncached", return_value=sample) as assess_once:
            first = vision.assess(b"fixture-frame")
            second = vision.assess(b"fixture-frame")
        self.assertEqual(assess_once.call_count, 1)
        self.assertEqual(first["cache"], "miss")
        self.assertEqual(second["cache"], "hit")
        self.assertEqual(second["box_2d"], [0.2, 0.1, 0.8, 0.7])

    def test_timeout_or_failure_returns_cant_tell(self):
        with patch("agni.vision._assess_uncached", return_value=vision._unknown("Timed out", "unavailable")):
            result = vision.assess(b"bad-frame")
        self.assertEqual(result["label"], "cant_tell")
        self.assertEqual(result["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
