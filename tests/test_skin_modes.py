import unittest

from src.services.skin_modes import (
    build_main_skin_overrides,
    get_effective_skin_mode,
    get_effective_skin_mode_for_slot,
    get_skin_cycle_modes,
    has_fixed_skin,
    has_random_skin,
    normalize_skin_mode,
    normalize_skin_override,
)


class SkinModesTests(unittest.TestCase):
    def test_normalize_skin_mode_accepts_known_modes(self):
        self.assertEqual(normalize_skin_mode(" FIXED "), "fixed")
        self.assertEqual(normalize_skin_mode("random"), "random")
        self.assertEqual(normalize_skin_mode("bad"), "none")

    def test_normalize_skin_override_accepts_inherit_and_modes(self):
        self.assertEqual(normalize_skin_override(" INHERIT "), "inherit")
        self.assertEqual(normalize_skin_override("none"), "none")
        self.assertEqual(normalize_skin_override("bad"), "inherit")

    def test_has_fixed_skin_checks_id_or_name(self):
        self.assertTrue(has_fixed_skin({"skin_id": "123"}))
        self.assertTrue(has_fixed_skin({"skin_name": "Default"}))
        self.assertFalse(has_fixed_skin({"skin_id": "bad", "skin_name": ""}))

    def test_has_random_skin_checks_preview_or_pool(self):
        self.assertTrue(has_random_skin({"random_skin_id": "123"}))
        self.assertTrue(has_random_skin({"random_skin_name": "Default"}))
        self.assertTrue(has_random_skin({"random_skin_pool": [{"skin_id": 123}]}))
        self.assertFalse(has_random_skin({"random_skin_id": "bad", "random_skin_name": "", "random_skin_pool": []}))

    def test_build_main_skin_overrides_uses_legacy_then_slot_values(self):
        overrides = build_main_skin_overrides(
            {
                "main_skin_mode_override": "fixed",
                "main_skin_mode_overrides": {
                    "pick_1": "inherit",
                    "pick_2": "random",
                    "pick_3": "bad",
                },
            }
        )

        self.assertEqual(overrides, {"pick_1": "inherit", "pick_2": "random", "pick_3": "inherit"})

    def test_get_effective_skin_mode_for_slot_uses_override_before_slot_mode(self):
        effective = {
            "pick_slots": {
                "pick_1": {"skin_mode": "random"},
                "pick_2": {"skin_mode": "fixed"},
            }
        }

        self.assertEqual(
            get_effective_skin_mode_for_slot("pick_1", effective, {"pick_1": "none"}),
            "none",
        )
        self.assertEqual(
            get_effective_skin_mode_for_slot("pick_1", effective, {"pick_1": "fixed"}),
            "fixed",
        )
        self.assertEqual(
            get_effective_skin_mode_for_slot("pick_2", effective, {"pick_2": "inherit"}),
            "fixed",
        )

    def test_get_effective_skin_mode_for_slot_can_fallback_to_pick_1(self):
        effective = {
            "pick_slots": {
                "pick_1": {"skin_mode": "random"},
                "pick_2": {},
            }
        }

        self.assertEqual(
            get_effective_skin_mode_for_slot(
                "pick_2",
                effective,
                {"pick_2": "inherit"},
                fallback_slot_key="pick_1",
            ),
            "random",
        )

    def test_get_effective_skin_mode_summarizes_slots(self):
        self.assertEqual(
            get_effective_skin_mode(
                {"pick_slots": {"pick_1": {"skin_mode": "none"}, "pick_2": {}, "pick_3": {}}},
                {},
            ),
            "none",
        )
        self.assertEqual(
            get_effective_skin_mode(
                {
                    "pick_slots": {
                        "pick_1": {"skin_mode": "fixed"},
                        "pick_2": {"skin_mode": "fixed"},
                        "pick_3": {"skin_mode": "fixed"},
                    }
                },
                {},
            ),
            "fixed",
        )
        self.assertEqual(
            get_effective_skin_mode(
                {
                    "pick_slots": {
                        "pick_1": {"skin_mode": "fixed"},
                        "pick_2": {"skin_mode": "random"},
                        "pick_3": {"skin_mode": "none"},
                    }
                },
                {},
            ),
            "mixed",
        )

    def test_get_skin_cycle_modes_for_slot_or_effective_profile(self):
        self.assertEqual(get_skin_cycle_modes(slot_data={}), ["none"])
        self.assertEqual(get_skin_cycle_modes(slot_data={"skin_id": 1}), ["none", "fixed"])
        self.assertEqual(get_skin_cycle_modes(slot_data={"random_skin_pool": [{"skin_id": 2}]}), ["none", "random"])
        self.assertEqual(
            get_skin_cycle_modes(
                effective={
                    "pick_slots": {
                        "pick_1": {"skin_id": 1},
                        "pick_2": {"random_skin_id": 2},
                        "pick_3": {},
                    }
                }
            ),
            ["none", "fixed", "random"],
        )


if __name__ == "__main__":
    unittest.main()
