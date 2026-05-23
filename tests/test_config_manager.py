import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class ConfigMigrationTests(unittest.TestCase):
    def setUp(self):
        fake_yaml = types.ModuleType("yaml")

        def safe_load(_stream):
            return {
                "portal": {
                    "login_url": "http://10.0.0.1/eportal/index.jsp",
                    "username": "student",
                    "password": "secret",
                },
                "keepalive": {"interval_seconds": 600},
                "auto_login": {"enabled": True},
                "logging": {"level": "INFO"},
            }

        def dump(data, stream, **_kwargs):
            stream.write(repr(data))

        fake_yaml.safe_load = safe_load
        fake_yaml.dump = dump
        sys.modules["yaml"] = fake_yaml

        if "config_manager" in sys.modules:
            del sys.modules["config_manager"]

    def test_legacy_config_loads_with_app_defaults(self):
        config_manager = importlib.import_module("config_manager")
        config_manager.HAS_CRYPTO = False

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text("legacy: true", encoding="utf-8")

            manager = config_manager.ConfigManager(config_path)
            config = manager.load()

        self.assertEqual(config.app.mode, "auto")
        self.assertFalse(config.app.start_minimized)
        self.assertTrue(config.app.show_notifications)
        self.assertEqual(
            config.portal.login_url,
            "http://192.168.2.135/eportal/success.jsp?",
        )

    def test_default_login_url_matches_campus_portal(self):
        config_manager = importlib.import_module("config_manager")
        config_manager.HAS_CRYPTO = False

        config = config_manager.AppConfig()

        self.assertEqual(
            config.portal.login_url,
            "http://192.168.2.135/eportal/success.jsp?",
        )

    def test_default_keepalive_interval_is_two_minutes(self):
        config_manager = importlib.import_module("config_manager")
        config_manager.HAS_CRYPTO = False

        config = config_manager.AppConfig()

        self.assertEqual(config.keepalive.interval_seconds, 120)

    def test_create_example_writes_to_configured_parent(self):
        config_manager = importlib.import_module("config_manager")
        config_manager.HAS_CRYPTO = False

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            manager = config_manager.ConfigManager(config_path)
            example_path = manager.create_example()

            self.assertEqual(example_path, Path(tmp) / "config.example.yaml")
            self.assertTrue(example_path.exists())

    def test_create_example_uses_two_minute_keepalive_interval(self):
        config_manager = importlib.import_module("config_manager")
        config_manager.HAS_CRYPTO = False

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            manager = config_manager.ConfigManager(config_path)
            example_path = manager.create_example()

            self.assertIn(
                "interval_seconds: 120",
                example_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
