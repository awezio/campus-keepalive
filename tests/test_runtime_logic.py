import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class ConfigFixtureMixin:
    def _config(
        self,
        *,
        mode="auto",
        login_url="http://192.168.2.135/eportal/success.jsp?",
        username="student",
        password="secret",
        auto_login_enabled=True,
    ):
        return SimpleNamespace(
            app=SimpleNamespace(mode=mode),
            portal=SimpleNamespace(
                login_url=login_url,
                username=username,
                password=password,
            ),
            auto_login=SimpleNamespace(enabled=auto_login_enabled),
        )


class RuntimeModeDecisionTests(ConfigFixtureMixin, unittest.TestCase):
    def test_auto_mode_uses_auto_login_when_portal_detected_and_credentials_complete(self):
        from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode

        result = decide_runtime_mode(
            self._config(mode="auto"),
            NetworkSnapshot(status="offline", redirect_url="http://10.0.0.1/login"),
        )

        self.assertEqual(result, RuntimeMode.AUTO_LOGIN)

    def test_auto_mode_starts_login_flow_when_only_login_url_is_configured(self):
        from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode

        result = decide_runtime_mode(
            self._config(mode="auto", username="", password=""),
            NetworkSnapshot(status="offline", redirect_url="http://10.0.0.1/login"),
        )

        self.assertEqual(result, RuntimeMode.AUTO_LOGIN)

    def test_auto_mode_uses_auto_login_when_external_access_fails_without_redirect(self):
        from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode

        for status in ("error", "disconnected"):
            with self.subTest(status=status):
                result = decide_runtime_mode(
                    self._config(mode="auto"),
                    NetworkSnapshot(status=status, redirect_url=None),
                )

                self.assertEqual(result, RuntimeMode.AUTO_LOGIN)

    def test_auto_mode_starts_login_flow_without_login_url_when_external_access_fails(self):
        from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode

        result = decide_runtime_mode(
            self._config(mode="auto", login_url="", username="", password=""),
            NetworkSnapshot(status="error", redirect_url=None),
        )

        self.assertEqual(result, RuntimeMode.AUTO_LOGIN)

    def test_explicit_keepalive_mode_wins_over_portal_detection(self):
        from mode_decider import NetworkSnapshot, RuntimeMode, decide_runtime_mode

        result = decide_runtime_mode(
            self._config(mode="keepalive_only"),
            NetworkSnapshot(status="offline", redirect_url="http://10.0.0.1/login"),
        )

        self.assertEqual(result, RuntimeMode.KEEPALIVE_ONLY)


class ReconnectGateTests(unittest.TestCase):
    def test_reconnect_gate_resets_after_exception(self):
        from service_controller import ReconnectGate

        gate = ReconnectGate()

        with self.assertRaises(RuntimeError):
            with gate:
                self.assertTrue(gate.active)
                raise RuntimeError("boom")

        self.assertFalse(gate.active)


class ServiceControllerStartupTests(ConfigFixtureMixin, unittest.TestCase):
    def test_start_delays_first_heartbeat_until_after_initial_check(self):
        from service_controller import ServiceController

        class FakeHeartbeat:
            def __init__(self):
                self.start_calls = []

            def start(self, run_immediately=True):
                self.start_calls.append(run_immediately)

        heartbeat = FakeHeartbeat()
        controller = ServiceController(self._config(mode="auto"))
        checks = []
        controller._heartbeat = heartbeat
        controller._ensure_heartbeat = lambda: heartbeat
        controller.check_now = lambda: checks.append("check")

        controller.start()

        self.assertEqual(heartbeat.start_calls, [False])
        self.assertEqual(checks, ["check"])


class ServiceControllerLoginFlowTests(ConfigFixtureMixin, unittest.TestCase):
    def test_heartbeat_error_triggers_reconnect_when_external_access_fails(self):
        from mode_decider import RuntimeMode
        from service_controller import ServiceController

        controller = ServiceController(self._config(mode="auto"))
        reconnects = []
        controller.reconnect_now = lambda: reconnects.append("reconnect")

        result = SimpleNamespace(
            status=SimpleNamespace(value="error"),
            redirect_url=None,
            message="All external URLs failed",
        )

        controller._on_heartbeat_error(result)

        self.assertEqual(controller.status.network_status, "error")
        self.assertEqual(controller.status.mode, RuntimeMode.AUTO_LOGIN)
        self.assertEqual(reconnects, ["reconnect"])

    def test_reconnect_opens_browser_when_saved_credentials_are_missing(self):
        from service_controller import ServiceController

        opened_urls = []
        controller = ServiceController(
            self._config(mode="auto", username="", password=""),
            browser_open=opened_urls.append,
        )

        thread = controller.reconnect_now()
        thread.join(timeout=1)

        self.assertEqual(opened_urls, ["http://192.168.2.135/eportal/success.jsp?"])
        self.assertIn("browser", controller.status.last_error.lower())

    def test_reconnect_opens_default_login_url_when_login_url_is_missing(self):
        from service_controller import ServiceController

        opened_urls = []
        controller = ServiceController(
            self._config(mode="auto", login_url="", username="", password=""),
            browser_open=opened_urls.append,
        )

        thread = controller.reconnect_now()
        thread.join(timeout=1)

        self.assertEqual(opened_urls, ["http://192.168.2.135/eportal/success.jsp?"])

    def test_reconnect_only_opens_browser_when_saved_credentials_exist(self):
        from service_controller import ServiceController

        opened_urls = []
        controller = ServiceController(
            self._config(mode="auto", username="student", password="secret"),
            browser_open=opened_urls.append,
        )
        auto_login_calls = []
        controller._ensure_auto_login = lambda: auto_login_calls.append("auto-login")

        thread = controller.reconnect_now()
        thread.join(timeout=1)

        self.assertEqual(opened_urls, ["http://192.168.2.135/eportal/success.jsp?"])
        self.assertEqual(auto_login_calls, [])
        self.assertIn("browser", controller.status.last_error.lower())

    def test_login_page_can_be_opened_again_after_cooldown_expires(self):
        from service_controller import ServiceController

        opened_urls = []
        controller = ServiceController(
            self._config(mode="auto", username="student", password="secret"),
            browser_open=opened_urls.append,
        )
        controller._browser_open_interval_seconds = 60

        with patch("service_controller.time.monotonic", side_effect=[100.0, 130.0, 161.0]):
            self.assertTrue(controller._open_login_page())
            self.assertFalse(controller._open_login_page())
            self.assertTrue(controller._open_login_page())

        self.assertEqual(
            opened_urls,
            ["http://192.168.2.135/eportal/success.jsp?", "http://192.168.2.135/eportal/success.jsp?"],
        )


if __name__ == "__main__":
    unittest.main()
