import unittest

from src.ui._picker_common import picker_lcu_status_message
from src.ui.skin_picker import (
    _confirm_unowned_skin_selection,
    _get_picker_image_url,
    _merge_catalog_and_owned_skins,
    _sort_skins_for_display,
)


class SkinPickerMergeTests(unittest.TestCase):
    def test_merge_catalog_and_owned_marks_unowned_entries(self):
        merged = _merge_catalog_and_owned_skins(
            [
                {
                    "skin_id": 1,
                    "skin_name": "Base",
                    "skin_num": 1,
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

    def test_merge_catalog_marks_default_skin_as_owned_without_lcu_inventory(self):
        merged = _merge_catalog_and_owned_skins(
            [
                {
                    "skin_id": 86000,
                    "skin_name": "default",
                    "skin_num": 0,
                    "tile_url": "tile-default",
                    "splash_url": "splash-default",
                },
                {
                    "skin_id": 86001,
                    "skin_name": "Sanguine Garen",
                    "skin_num": 1,
                    "tile_url": "tile-1",
                    "splash_url": "splash-1",
                },
            ],
            [],
        )

        self.assertTrue(merged[0]["owned"])
        self.assertFalse(merged[1]["owned"])

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

    def test_sort_skins_for_display_prioritizes_selected_fixed_skin(self):
        skins = [
            {"skin_id": 1, "skin_name": "A"},
            {"skin_id": 2, "skin_name": "B"},
            {"skin_id": 3, "skin_name": "C"},
        ]

        ordered = _sort_skins_for_display(skins, mode="fixed", fixed_skin_id=2)

        self.assertEqual([skin["skin_id"] for skin in ordered], [2, 1, 3])

    def test_sort_skins_for_display_prioritizes_random_pool(self):
        skins = [
            {"skin_id": 1, "skin_name": "A"},
            {"skin_id": 2, "skin_name": "B"},
            {"skin_id": 3, "skin_name": "C"},
        ]

        ordered = _sort_skins_for_display(skins, mode="random", pool_ids={3, 1})

        self.assertEqual([skin["skin_id"] for skin in ordered], [1, 3, 2])

    def test_confirm_unowned_skin_selection_skips_prompt_for_owned_skin(self):
        prompts = []

        result = _confirm_unowned_skin_selection(
            {"skin_id": 1, "skin_name": "Owned", "owned": True},
            ask_fn=lambda *args, **kwargs: prompts.append((args, kwargs)),
        )

        self.assertTrue(result)
        self.assertEqual(prompts, [])

    def test_confirm_unowned_skin_selection_uses_prompt_result(self):
        self.assertTrue(
            _confirm_unowned_skin_selection(
                {"skin_id": 2, "skin_name": "Unknown", "owned": False},
                ask_fn=lambda *args, **kwargs: True,
            )
        )
        self.assertFalse(
            _confirm_unowned_skin_selection(
                {"skin_id": 2, "skin_name": "Unknown", "owned": False},
                ask_fn=lambda *args, **kwargs: False,
            )
        )

    def test_confirm_unowned_skin_lcu_unavailable_shows_different_message(self):
        """When LCU is not available the prompt uses the client-not-detected wording."""
        captured_title = []
        captured_message = []

        def capture(title, message):
            captured_title.append(title)
            captured_message.append(message)
            return True

        result = _confirm_unowned_skin_selection(
            {"skin_id": 2, "skin_name": "Unknown", "owned": False},
            ask_fn=capture,
            lcu_available=False,
        )

        self.assertTrue(result)
        self.assertIn("LoL client not detected", captured_title[0])
        self.assertIn("Unable to verify", captured_message[0])

    def test_picker_lcu_status_message_uses_standard_wording(self):
        self.assertEqual(
            picker_lcu_status_message("skins"),
            "Unable to fetch skins: LoL client is not detected. Launch League of Legends to refresh.",
        )
        self.assertEqual(
            picker_lcu_status_message("runes"),
            "Unable to fetch runes: LoL client is not detected. Launch League of Legends to refresh.",
        )


if __name__ == "__main__":
    unittest.main()
