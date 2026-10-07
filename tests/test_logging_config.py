import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.logging_config import configure_logging


class LoggingConfigurationTests(unittest.TestCase):
    def test_configured_level_is_applied_to_root_logger(self) -> None:
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        try:
            configure_logging("warning")
            self.assertEqual(root_logger.level, logging.WARNING)
        finally:
            root_logger.setLevel(previous_level)

    def test_invalid_level_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "LOG_LEVEL"):
            configure_logging("not-a-level")

    def test_application_startup_fails_clearly_without_signing_key(self) -> None:
        from app.main import initialize_database

        with (
            patch("app.main.settings", SimpleNamespace(secret_key=None, environment="testing")),
            patch("app.main.init_db") as init_db,
        ):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY.*configured"):
                initialize_database()

        init_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
