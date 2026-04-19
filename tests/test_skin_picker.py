import unittest

from src.ui.skin_picker import _get_picker_image_url, _merge_catalog_and_owned_skins


class SkinPickerMergeTests(unittest.TestCase):
    def test_merge_catalog_and_owned_marks_unowned_entries(self):
        merged = _merge_catalog_and_owned_skins(
            [
                {
                    "skin_id": 1,
                    "skin_name": "Base",
                    "skin_num": 0,
                    "tile_url": "tile-1",
                    "splash_url": "splash-1",
                },
                {
                    "skin_id": 2,
                    "skin_name": "Fancy",
                    "skin_num": 1,
                    "tile_url": "tile-2",
                    "splash_url": "splash-2",
                },
            ],
            [
                {
                    "skin_id": 2,
                    "skin_name": "Fancy",
                    "skin_num": 1,
                    "preview_url": "owned-preview-2",
                }
            ],
        )

        self.assertEqual(len(merged), 2)
        self.assertFalse(merged[0]["owned"])
        self.assertEqual(merged[0]["preview_url"], "tile-1")
        self.assertTrue(merged[1]["owned"])
        self.assertEqual(merged[1]["preview_url"], "owned-preview-2")

    def test_picker_image_url_prefers_splash_over_tile(self):
        self.assertEqual(
            _get_picker_image_url(
                {
                    "tile_url": "tile-2",
                    "splash_url": "splash-2",
                    "centered_splash_url": "centered-2",
                    "uncentered_splash_url": "uncentered-2",
                }
            ),
            "centered-2",
        )

    def test_picker_image_url_skips_uncentered_fallback(self):
        self.assertEqual(
            _get_picker_image_url(
                {
                    "tile_url": "tile-2",
                    "splash_url": "splash-2",
                    "uncentered_splash_url": "uncentered-2",
                }
            ),
            "splash-2",
        )


if __name__ == "__main__":
    unittest.main()
