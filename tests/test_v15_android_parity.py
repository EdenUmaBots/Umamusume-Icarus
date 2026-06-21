"""v1.5 Phase 1 — android-parity training/charm changes.

Covers the clean, threshold-safe levers that fix Icarus's Power-over/Wit-under
allocation and unused Good-Luck Charms, without inflating score magnitude (which
would mis-fire the race-vs-train gates):
  * Wit damping + full-HP-Wit ban default OFF;
  * training selection is charm-aware (risky high-stat trainings become eligible
    when a Good-Luck Charm is held);
  * the baseline stat-priority multiplier stays OFF by default (targets encode
    priority instead).
The retry-policy and target-retune changes are covered by test_v6712_fixes and
test_v6710_fixes / the Oguri profile.
"""
import json
import os
import unittest

from career_bot.scenarios.mant import MantStrategy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def training(command_id=101, gain=40, failure=0, partners=None, tips=None):
    main_target = {101: 1, 105: 2, 102: 3, 103: 4, 106: 5}.get(command_id, 1)
    return {
        "command_type": 1, "command_id": command_id, "command_group_id": 0,
        "select_id": 0, "is_enable": 1, "failure_rate": failure,
        "training_partner_array": partners or [], "tips_event_partner_array": tips or [],
        "params_inc_dec_info_array": [{"target_type": main_target, "value": gain}],
    }


def data_with_charm(qty):
    return {"free_data_set": {"user_item_info_array": [{"item_id": 10001, "num": qty}]}}


class CharmAwareTrainingTests(unittest.TestCase):
    def setUp(self):
        self.s = MantStrategy()
        # A risky speed training: 45% failure but a big main gain.
        self.risky = training(101, gain=50, failure=45)

    def test_risky_blocked_without_charm(self):
        self.assertFalse(self.s._failure_allowed(self.risky, {"mant_config": {}}, has_charm=False))

    def test_risky_allowed_with_charm(self):
        self.assertTrue(self.s._failure_allowed(self.risky, {"mant_config": {}}, has_charm=True))

    def test_low_gain_risky_still_blocked_with_charm(self):
        weak = training(101, gain=10, failure=45)  # gain below charm_min_main_gain(30)
        self.assertFalse(self.s._failure_allowed(weak, {"mant_config": {}}, has_charm=True))

    def test_can_disable_charm_awareness(self):
        off = {"mant_config": {"enable_charm_aware_training": False}}
        self.assertFalse(self.s._failure_allowed(self.risky, off, has_charm=True))

    def test_score_command_surfaces_risky_training_when_charm_held(self):
        # _score_command must NOT return the -999 reject for a risky training
        # when a charm is in inventory.
        chara = {"turn": 20, "speed": 300, "stamina": 300, "power": 300, "guts": 300, "wiz": 300}
        score_charm = self.s._score_command(self.risky, data_with_charm(1), chara, {"mant_config": {}, "compensate_failure": False})
        score_none = self.s._score_command(self.risky, data_with_charm(0), chara, {"mant_config": {}, "compensate_failure": False})
        self.assertGreater(score_charm, -900)
        self.assertEqual(score_none, -999.0)


class WitSuppressionDefaultsTests(unittest.TestCase):
    def test_wit_balance_damping_off_by_default(self):
        s = MantStrategy()
        chara = {"speed": 300, "stamina": 300, "power": 300, "guts": 300, "wiz": 900}
        targets = [1000, 1000, 1000, 1000, 1000]
        # Wit far ahead of the others -> old code returned 0.72; now 1.0.
        self.assertEqual(s._wit_balance_multiplier(chara, targets, {"mant_config": {}}), 1.0)

    def test_full_hp_rainbow_wit_allowed_by_default(self):
        s = MantStrategy()
        wit = training(106, gain=40, partners=[1])
        chara = {"vital": 100, "max_vital": 100,
                 "evaluation_info_array": [{"target_id": 1, "evaluation": 80}]}
        # rainbow Wit at full HP is no longer auto-avoided.
        self.assertFalse(s._should_avoid_full_hp_wit(wit, chara, {"mant_config": {}}))


class PriorityMultiplierDefaultTests(unittest.TestCase):
    def test_priority_multiplier_off_by_default(self):
        s = MantStrategy()
        preset = {"mant_config": {"training_stat_priority": ["speed", "power", "stamina", "wit", "guts"]}}
        # Default OFF -> 1.0 (no score inflation that would break race-vs-train gates).
        self.assertEqual(s._stat_priority_multiplier(0, preset, turn=20), 1.0)
        # Opt-in restores android-style weighting.
        preset["mant_config"]["enable_stat_priority_weighting"] = True
        self.assertAlmostEqual(s._stat_priority_multiplier(0, preset, turn=20), 3.5)


class OguriTargetTests(unittest.TestCase):
    def test_power_target_below_wit(self):
        prof = json.load(open(os.path.join(BASE_DIR, "data", "character_profiles", "oguri_cap.json"), encoding="utf-8"))
        # navigate to the stat_targets block regardless of nesting
        def find_targets(o):
            if isinstance(o, dict):
                if "mile" in o and isinstance(o["mile"], dict) and "power" in o["mile"]:
                    return o
                for v in o.values():
                    r = find_targets(v)
                    if r:
                        return r
            return None
        targets = find_targets(prof)
        self.assertIsNotNone(targets)
        self.assertLess(targets["mile"]["power"], targets["mile"]["wit"],
                        "Oguri mile Power target must be below Wit to match android's 761/919 build")
        self.assertLessEqual(targets["mile"]["power"], 900)


if __name__ == "__main__":
    unittest.main()
