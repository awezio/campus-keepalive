import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class FakeResponse:
    def __init__(self, status_code, headers=None, body=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = body

        class Raw:
            def __init__(self, value):
                self._value = value

            def read(self, _size):
                return self._value

        self.raw = Raw(body)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def head(self, url, **kwargs):
        self.calls.append(("HEAD", url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class NetworkCheckerProbeTests(unittest.TestCase):
    def test_get_fallback_marks_online_when_head_is_rejected(self):
        import requests
        from network_checker import NetworkChecker, NetworkStatus

        checker = NetworkChecker(check_urls=[("http://example.test", "example")])
        checker.session = FakeSession([
            requests.exceptions.ConnectionError("head rejected"),
            FakeResponse(200),
        ])

        result = checker.check()

        self.assertEqual(result.status, NetworkStatus.ONLINE)
        self.assertEqual([call[0] for call in checker.session.calls], ["HEAD", "GET"])

    def test_windows_captive_portal_redirect_is_reported_as_login_required(self):
        from network_checker import NetworkChecker, NetworkStatus

        login_url = "http://192.168.2.135/eportal/success.jsp?"
        checker = NetworkChecker(check_urls=[(NetworkChecker.WINDOWS_NCSI_URL, "windows_ncsi")])
        checker.session = FakeSession([
            FakeResponse(302, headers={"Location": login_url}),
        ])

        result = checker.check()

        self.assertEqual(result.status, NetworkStatus.OFFLINE)
        self.assertEqual(result.redirect_url, login_url)

    def test_login_form_html_from_probe_is_reported_as_login_required(self):
        from network_checker import NetworkChecker, NetworkStatus

        checker = NetworkChecker(check_urls=[("http://example.test", "example")])
        checker.session = FakeSession([
            FakeResponse(200, body=b'<form><input type="password" name="password"></form>'),
        ])

        result = checker.check()

        self.assertEqual(result.status, NetworkStatus.OFFLINE)
        self.assertEqual(result.redirect_url, "http://example.test")


if __name__ == "__main__":
    unittest.main()
