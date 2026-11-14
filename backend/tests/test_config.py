import os
import unittest
from unittest.mock import patch

from agni.config import _flag


class ConfigTests(unittest.TestCase):
    def test_empty_env_value_uses_safe_default(self):
        with patch.dict(os.environ, {"AGNI_MOCK": ""}, clear=False):
            self.assertTrue(_flag("AGNI_MOCK", True))

    def test_explicit_off_value_is_false(self):
        with patch.dict(os.environ, {"OVERFLOW_ENABLED": "0"}, clear=False):
            self.assertFalse(_flag("OVERFLOW_ENABLED", True))


if __name__ == "__main__":
    unittest.main()
