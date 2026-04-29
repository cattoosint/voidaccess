"""Tests for config.py"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock


class TestConfigOTXKey(unittest.TestCase):
    """Test that OTX_API_KEY is correctly loaded from environment."""

    def test_otx_api_key_from_environment(self):
        """OTX_API_KEY should be loaded from environment, not overwritten."""
        test_key = "test-key-123"

        for mod_name in list(sys.modules.keys()):
            if mod_name == "voidaccess.config" or mod_name.startswith("voidaccess.config."):
                sys.modules.pop(mod_name)

        env = {
            "JWT_SECRET": "test-secret-for-validation",
            "OTX_API_KEY": test_key,
        }

        with patch.dict(os.environ, env, clear=True):
            import voidaccess.config as config
            import importlib
            importlib.reload(config)

            self.assertEqual(config.OTX_API_KEY, test_key)


class TestConfigValidation(unittest.TestCase):
    """Test config validation."""

    def test_validate_config_logs_warning_for_missing_optional(self):
        """validate_config should log warning for missing optional keys."""
        for mod_name in list(sys.modules.keys()):
            if mod_name == "voidaccess.config" or mod_name.startswith("voidaccess.config."):
                sys.modules.pop(mod_name)

        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key-123"}, clear=True):
            import voidaccess.config as config_module
            import logging
            import importlib
            importlib.reload(config_module)

            with patch("voidaccess.config.logger") as mock_logger:
                config_module.validate_config()

                self.assertTrue(mock_logger.warning.called)
                warning_calls = str(mock_logger.warning.call_args_list)
                self.assertIn("OPENAI_API_KEY", warning_calls)


if __name__ == "__main__":
    unittest.main()