import unittest

from src.services.profile_config import build_effective_profile_config


class ProfileConfigTests(unittest.TestCase):
    def test_build_effective_profile_config_uses_selected_pick_keys(self):
        effective = build_effective_profile_config(
            {
                "presets_enabled": True,
                "selected_pick_1": "Garen",
                "selected_pick_2": "Lux",
                "selected_pick_3": "Ashe",
                "selected_ban": "Teemo",
                "pick_slots": {
                    "pick_1": {"spell_1": "Ghost", "spell_2": "Flash"},
                    "pick_2": {"spell_1": "Heal", "spell_2": "Flash"},
                    "pick_3": {"spell_1": "Barrier", "spell_2": "Ignite"},
                },
            }
        )

        self.assertEqual(effective["selected_pick_1"], "Garen")
        self.assertEqual(effective["selected_pick_2"], "Lux")
        self.assertEqual(effective["selected_pick_3"], "Ashe")
        self.assertEqual(effective["selected_ban"], "Teemo")
        self.assertEqual(effective["spell_1"], "Ghost")
        self.assertEqual(effective["spell_2"], "Flash")
        self.assertEqual(effective["pick_slots"]["pick_1"]["champion"], "Garen")
        self.assertEqual(effective["pick_slots"]["pick_2"]["champion"], "Lux")
        self.assertEqual(effective["pick_slots"]["pick_3"]["champion"], "Ashe")

    def test_build_effective_profile_config_normalizes_slot_values(self):
        effective = build_effective_profile_config(
            {
                "selected_pick_1": "Garen",
                "selected_pick_2": "Lux",
                "selected_pick_3": "Ashe",
                "pick_slots": {
                    "pick_1": {
                        "skin_mode": " FIXED ",
                        "skin_id": "86013",
                        "skin_num": "13",
                        "random_skin_id": "bad",
                        "random_skin_pool": [{"skin_id": 86013}, "ignored"],
                        "rune_page_id": "123",
                        "rune_page_name": "Top Runes",
                        "rune_auto_apply": False,
                        "rune_keystone_path": "keystone.png",
                        "rune_sub_style_icon_path": "substyle.png",
                    }
                },
            }
        )

        slot = effective["pick_slots"]["pick_1"]
        self.assertEqual(slot["skin_mode"], "fixed")
        self.assertEqual(slot["skin_id"], 86013)
        self.assertEqual(slot["skin_num"], 13)
        self.assertEqual(slot["random_skin_id"], 0)
        self.assertEqual(slot["random_skin_pool"], [{"skin_id": 86013}])
        self.assertEqual(slot["rune_page_id"], 123)
        self.assertEqual(slot["rune_page_name"], "Top Runes")
        self.assertFalse(slot["rune_auto_apply"])
        self.assertEqual(slot["rune_keystone_path"], "keystone.png")
        self.assertEqual(slot["rune_sub_style_icon_path"], "substyle.png")


if __name__ == "__main__":
    unittest.main()
