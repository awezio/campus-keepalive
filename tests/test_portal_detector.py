import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class PortalDetectorTests(unittest.TestCase):
    def test_private_eportal_url_is_recognized_as_login_page(self):
        if "requests" not in sys.modules:
            sys.modules["requests"] = types.ModuleType("requests")

        if "portal_detector" in sys.modules:
            del sys.modules["portal_detector"]

        from portal_detector import PortalDetector

        detector = PortalDetector()

        self.assertTrue(detector._is_login_page("http://10.0.0.1/eportal/index.jsp"))


if __name__ == "__main__":
    unittest.main()
