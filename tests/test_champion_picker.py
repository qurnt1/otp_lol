import unittest

from src.services.champion_roles import champion_matches_role, fallback_positions_from_tags, role_score, sort_champions_for_role


class FakeDataDragon:
    def __init__(self, tags_by_champion):
        self.tags_by_champion = tags_by_champion

    def get_champion_tags(self, champion_name):
        return self.tags_by_champion.get(champion_name, [])


class ChampionPickerRoleFilterTests(unittest.TestCase):
    def test_global_role_matches_every_champion(self):
        dd = FakeDataDragon({"Garen": ["Fighter", "Tank"]})

        self.assertTrue(champion_matches_role(dd, "Garen", "GLOBAL"))

    def test_curated_role_data_matches_multi_role_champion(self):
        dd = FakeDataDragon({})

        self.assertTrue(champion_matches_role(dd, "Lux", "UTILITY"))
        self.assertTrue(champion_matches_role(dd, "Lux", "MIDDLE"))
        self.assertFalse(champion_matches_role(dd, "Lux", "TOP"))

    def test_role_score_uses_curated_dataset_before_tags(self):
        dd = FakeDataDragon({"Lux": ["Mage", "Support"]})

        self.assertEqual(role_score(dd, "Lux", "UTILITY"), 0.55)

    def test_fallback_roles_are_built_from_datadragon_tags(self):
        scores = fallback_positions_from_tags(["Marksman", "Support"])

        self.assertGreaterEqual(scores["BOTTOM"], 0.75)
        self.assertGreaterEqual(scores["UTILITY"], 0.75)

    def test_missing_curated_data_falls_back_to_tags(self):
        dd = FakeDataDragon({"Unknown Champ": ["Marksman"]})

        self.assertTrue(champion_matches_role(dd, "Unknown Champ", "BOTTOM"))
        self.assertFalse(champion_matches_role(dd, "Unknown Champ", "TOP"))

    def test_sort_champions_for_role_orders_by_score_then_name(self):
        dd = FakeDataDragon({})

        ordered = sort_champions_for_role(["Lux", "Garen", "Ahri"], dd, "MIDDLE")

        self.assertEqual(ordered, ["Ahri", "Lux", "Garen"])


if __name__ == "__main__":
    unittest.main()
