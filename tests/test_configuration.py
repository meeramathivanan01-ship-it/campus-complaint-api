import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import PROJECT_ROOT, load_settings
from app.security import create_access_token


class ConfigurationTests(unittest.TestCase):
    def test_dotenv_configuration_loads_without_overriding_process_environment(self) -> None:
        env_file = PROJECT_ROOT / "fixture.env"
        environ = {"SECRET_KEY": "process-only-key"}
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(
                Path,
                "read_text",
                return_value=(
                    "SECRET_KEY='test-only-key'\n"
                "DATABASE_PATH=tmp/test.sqlite\n"
                "ENVIRONMENT=testing\n"
                "LOG_LEVEL=warning\n"
                ),
            ),
        ):
            settings = load_settings(env_file, environ)

        self.assertEqual(settings.secret_key, "process-only-key")
        self.assertEqual(
            settings.database_path,
            PROJECT_ROOT / "tmp" / "test.sqlite",
        )
        self.assertEqual(settings.environment, "testing")
        self.assertEqual(settings.log_level, "WARNING")
        self.assertNotIn("process-only-key", repr(settings))

    def test_missing_secret_has_no_insecure_fallback_and_token_creation_fails_clearly(
        self,
    ) -> None:
        settings = load_settings(PROJECT_ROOT / "missing-test-config.env", {})

        self.assertIsNone(settings.secret_key)
        with patch("app.security.SECRET_KEY", settings.secret_key):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY.*configured"):
                create_access_token(1, "student")

    def test_default_configuration_keeps_project_sqlite_location(self) -> None:
        settings = load_settings(PROJECT_ROOT / "missing-test-config.env", {})

        self.assertEqual(
            settings.database_path,
            PROJECT_ROOT / "campus_complaints.db",
        )
        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.log_level, "INFO")


if __name__ == "__main__":
    unittest.main()
