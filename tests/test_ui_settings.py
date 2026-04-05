import unittest

from src.ui.settings_window import SettingsWindow


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeParent:
    def __init__(self):
        self.params = {
            "selected_profile_role": "MIDDLE",
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "global_spell_1": "Heal",
            "global_spell_2": "Flash",
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "theme": "darkly",
            "role_profiles": {
                "MIDDLE": {
                    "selected_pick_1": "Ahri",
                    "selected_pick_2": "",
                    "selected_pick_3": "",
                    "selected_ban": "Zed",
                    "spell_1": "Ignite",
                    "spell_2": "",
                }
            },
        }

    def get_params(self):
        return self.params

    def update_param(self, key, value):
        self.params[key] = value


class SettingsWindowLogicTests(unittest.TestCase):
    def make_window(self):
        window = SettingsWindow.__new__(SettingsWindow)
        window.parent = FakeParent()
        window.profile_role_var = DummyVar("MIDDLE")
        return window

    def test_get_profile_role_data_includes_spells(self):
        window = self.make_window()

        data = window._get_profile_role_data()

        self.assertEqual(data["selected_pick_1"], "Ahri")
        self.assertEqual(data["spell_1"], "Ignite")
        self.assertEqual(data["spell_2"], "")

    def test_get_excluded_champions_for_ban_includes_picks(self):
        window = self.make_window()

        excluded = window._get_excluded_champions("ban")

        self.assertEqual(excluded, {"Ahri"})

    def test_set_profile_value_updates_role_profile_payload(self):
        window = self.make_window()

        window._set_profile_value("spell_2", "Flash")

        self.assertEqual(window.parent.params["role_profiles"]["MIDDLE"]["spell_2"], "Flash")

    def test_stats_site_selection_updates_parent_config(self):
        window = self.make_window()

        class DummyCombo:
            def get(self):
                return "DeepLOL"

        window.stats_site_cb = DummyCombo()
        window.preferred_stats_site_var = DummyVar("opgg")

        window._on_stats_site_selected()

        self.assertEqual(window.parent.params["preferred_stats_site"], "deeplol")
        self.assertEqual(window.preferred_stats_site_var.get(), "deeplol")

    def test_hotkey_site_selection_updates_parent_config(self):
        window = self.make_window()

        class DummyCombo:
            def get(self):
                return "OP.GG"

        window.hotkey_site_cb = DummyCombo()
        window.preferred_hotkey_site_var = DummyVar("porofessor")

        window._on_hotkey_site_selected()

        self.assertEqual(window.parent.params["preferred_hotkey_site"], "opgg")
        self.assertEqual(window.preferred_hotkey_site_var.get(), "opgg")


if __name__ == "__main__":
    unittest.main()
