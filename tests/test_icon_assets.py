import sys
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class IconAssetTests(unittest.TestCase):
    def _ico_sizes(self, path):
        with Image.open(path) as image:
            if hasattr(image, "ico"):
                return set(image.ico.sizes())
            sizes = []
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                sizes.append(image.size)
            return set(sizes)

    def test_app_icon_contains_windows_icon_sizes(self):
        expected = {(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}

        self.assertTrue(expected.issubset(self._ico_sizes(ROOT / "assets" / "icon.ico")))

    def test_tray_status_icons_exist_and_have_small_sizes(self):
        expected_small = {(16, 16), (20, 20), (24, 24), (32, 32)}

        for name in ("tray-online.ico", "tray-connecting.ico", "tray-offline.ico", "tray-paused.ico"):
            with self.subTest(name=name):
                path = ROOT / "assets" / "icons" / name
                self.assertTrue(path.exists(), f"{path} is missing")
                self.assertTrue(expected_small.issubset(self._ico_sizes(path)))


if __name__ == "__main__":
    unittest.main()
