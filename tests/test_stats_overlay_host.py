import unittest
from unittest.mock import patch

from src.ui import stats_overlay_host


class StatsOverlayHostTests(unittest.TestCase):
    def test_compute_overlay_geometry_centers_overlay_inside_work_area(self):
        with patch("src.ui.stats_overlay_host.get_work_area", return_value=(100, 50, 1700, 950)):
            width, height, x, y = stats_overlay_host.compute_overlay_geometry(0.92, 0.88)

        self.assertEqual(width, 1472)
        self.assertEqual(height, 792)
        self.assertEqual(x, 164)
        self.assertEqual(y, 104)

    def test_compute_overlay_geometry_clamps_extreme_ratios(self):
        with patch("src.ui.stats_overlay_host.get_work_area", return_value=(0, 0, 1280, 720)):
            width, height, x, y = stats_overlay_host.compute_overlay_geometry(5.0, 0.1)

        self.assertEqual(width, 1254)
        self.assertEqual(height, 700)
        self.assertEqual(x, 13)
        self.assertEqual(y, 10)


if __name__ == "__main__":
    unittest.main()
