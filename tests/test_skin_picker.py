import unittest
from unittest.mock import Mock

from src.services.skin_catalog import (
    confirm_unowned_skin_selection,
    get_picker_image_url,
    merge_catalog_and_owned_skins,
    picker_lcu_status_message,
    sort_skins_for_display,
)


class SkinCatalogTests(unittest.TestCase):
    def test_merge_catalog_and_owned_marks_unowned_entries(self):
        catalog = [
            {"skin_id": 1000, "skin_num": 0, "skin_name": "Default", "tile_url": "default"},
            {"skin_id": 1001, "skin_num": 1, "skin_name": "Owned", "tile_url": "owned"},
            {"skin_id": 1002, "skin_num": 2, "skin_name": "Other", "tile_url": "other"},
        ]
        merged = merge_catalog_and_owned_skins(
            catalog,
            [{"skin_id": 1001, "skin_num": 1, "skin_name": "Owned", "owned": True}],
        )
        by_id = {skin["skin_id"]: skin for skin in merged}
        self.assertTrue(by_id[1000]["owned"])
        self.assertTrue(by_id[1001]["owned"])
        self.assertFalse(by_id[1002]["owned"])

    def test_merge_adds_owned_entries_missing_from_catalog(self):
        merged = merge_catalog_and_owned_skins(
            [],
            [{"skin_id": 2001, "skin_num": 1, "skin_name": "Legacy", "tile_url": "tile"}],
        )
        self.assertEqual(merged[0]["skin_name"], "Legacy")
        self.assertTrue(merged[0]["owned"])

    def test_picker_image_url_prefers_centered_splash(self):
        self.assertEqual(
            get_picker_image_url(
                {
                    "centered_splash_url": "centered",
                    "splash_url": "splash",
                    "tile_url": "tile",
                }
            ),
            "centered",
        )

    def test_picker_image_url_skips_uncentered_fallback(self):
        self.assertEqual(
            get_picker_image_url({"uncentered_splash_url": "uncentered", "tile_url": "tile"}),
            "tile",
        )

    def test_sort_prioritizes_selected_fixed_skin(self):
        skins = [{"skin_id": 1}, {"skin_id": 2}, {"skin_id": 3}]
        self.assertEqual(
            [skin["skin_id"] for skin in sort_skins_for_display(skins, mode="fixed", fixed_skin_id=3)],
            [3, 1, 2],
        )

    def test_sort_prioritizes_random_pool(self):
        skins = [{"skin_id": 1}, {"skin_id": 2}, {"skin_id": 3}]
        self.assertEqual(
            [skin["skin_id"] for skin in sort_skins_for_display(skins, mode="random", pool_ids={2, 3})],
            [2, 3, 1],
        )

    def test_owned_skin_skips_confirmation(self):
        ask = Mock(return_value=False)
        self.assertTrue(confirm_unowned_skin_selection({"owned": True}, ask_fn=ask))
        ask.assert_not_called()

    def test_unowned_skin_uses_confirmation_result(self):
        ask = Mock(return_value=True)
        self.assertTrue(confirm_unowned_skin_selection({"owned": False}, ask_fn=ask))
        ask.assert_called_once()

    def test_offline_unowned_warning_mentions_client_detection(self):
        calls = []

        def ask(title, message):
            calls.append((title, message))
            return False

        self.assertFalse(
            confirm_unowned_skin_selection(
                {"owned": False},
                ask_fn=ask,
                lcu_available=False,
            )
        )
        self.assertIn("not detected", calls[0][0].lower())
        self.assertIn("offline", calls[0][1].lower())

    def test_picker_lcu_status_message_uses_standard_wording(self):
        self.assertEqual(
            picker_lcu_status_message("skins"),
            "Unable to fetch skins: LoL client is not detected. Launch League of Legends to refresh.",
        )


if __name__ == "__main__":
    unittest.main()
