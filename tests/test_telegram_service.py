import unittest

from src.services.telegram import TelegramService


class DummyDataDragon:
    def __init__(self):
        self.mapping = {
            "garen": 86,
            "lux": 99,
            "ashe": 22,
            "teemo": 17,
        }
        self.reverse = {
            86: "Garen",
            99: "Lux",
            22: "Ashe",
            17: "Teemo",
        }

    def resolve_champion(self, name_or_id):
        if isinstance(name_or_id, int):
            return name_or_id
        return self.mapping.get(str(name_or_id).strip().lower())

    def id_to_name(self, champion_id):
        return self.reverse.get(champion_id)


class TelegramServiceTests(unittest.TestCase):
    def make_service(self):
        params = {
            "selected_profile_role": "MIDDLE",
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
            "selected_pick_1": "Garen",
            "selected_pick_2": "Lux",
            "selected_pick_3": "Ashe",
            "selected_ban": "Teemo",
            "global_spell_1": "Heal",
            "global_spell_2": "Flash",
            "auto_pick_enabled": True,
            "auto_ban_enabled": True,
            "auto_accept_enabled": True,
            "auto_summoners_enabled": True,
            "auto_play_again_enabled": False,
            "preferred_stats_site": "opgg",
            "preferred_hotkey_site": "porofessor",
            "manual_summoner_name": "Tester#EUW",
            "telegram_remote_control_enabled": True,
        }
        commits = []

        def get_params():
            return params.copy()

        def update_param(key, value):
            params[key] = value

        def get_snapshot():
            return {
                "connected": True,
                "phase": "ChampSelect",
                "phase_label": "Selection des champions",
                "riot_id": "Tester#EUW",
                "region": "euw",
                "detected_role": "MIDDLE",
                "selected_profile_role": params.get("selected_profile_role", "GLOBAL"),
                "effective": {
                    "selected_pick_1": "Lux",
                    "selected_pick_2": "Ashe",
                    "selected_pick_3": "",
                    "selected_ban": "Teemo",
                    "spell_1": "Ignite",
                    "spell_2": "Flash",
                },
                "params": params,
                "lcu": {
                    "retry_count": 2,
                    "endpoint_error_count": 1,
                    "reconnect_count": 3,
                    "last_error": "",
                },
            }

        service = TelegramService(
            dd=DummyDataDragon(),
            get_params=get_params,
            update_param=update_param,
            save_params=lambda: None,
            get_snapshot=get_snapshot,
            commit_remote_changes=lambda message=None: commits.append(message),
        )
        return service, params, commits

    def test_set_pick_command_updates_current_role_profile(self):
        service, params, _ = self.make_service()

        response, _, changed = service._execute_command("/set_pick1 Lux")

        self.assertTrue(changed)
        self.assertEqual(response, "Pick 1 mis a jour: Lux")
        self.assertEqual(params["role_profiles"]["MIDDLE"]["selected_pick_1"], "Lux")

    def test_set_spells_command_updates_role_profile(self):
        service, params, _ = self.make_service()

        response, _, changed = service._execute_command("/set_spells Flash Ignite")

        self.assertTrue(changed)
        self.assertIn("Sorts mis a jour", response)
        self.assertEqual(params["role_profiles"]["MIDDLE"]["spell_1"], "Flash")
        self.assertEqual(params["role_profiles"]["MIDDLE"]["spell_2"], "Ignite")

    def test_enable_disable_commands_toggle_features(self):
        service, params, _ = self.make_service()

        response, _, changed = service._execute_command("/disable autopick")

        self.assertTrue(changed)
        self.assertEqual(response, "auto_pick_enabled -> OFF")
        self.assertFalse(params["auto_pick_enabled"])

    def test_status_text_includes_lcu_diagnostics(self):
        service, _, _ = self.make_service()

        text = service._build_status_text()

        self.assertIn("LCU retries GET: 2", text)
        self.assertIn("LCU reconnexions: 3", text)
        self.assertIn("Profil actif", text)


if __name__ == "__main__":
    unittest.main()
