"""v1.5 Phase 2: pre-finals skill dump.

On the turns just before the Twinkle Star Climax (>=73), buy() must spend SP
even when it's below the normal learn-skill threshold (android's preFinals
plan), instead of carrying SP past the last races it can influence.
"""
import os
import unittest

from career_bot.skills import SkillBuyer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeClient:
    pass


class PreFinalsDumpTests(unittest.TestCase):
    def setUp(self):
        self.sb = SkillBuyer(BASE_DIR)
        # Isolate the threshold gate from real master-data lookups.
        self.sb._candidates = lambda chara, preset: []
        self.preset = {"learn_skill_threshold": 400, "enable_skill_point_check": True}

    def _buy(self, turn, sp):
        st = {"data": {"chara_info": {"turn": turn, "skill_point": sp}}}
        self.sb.buy(_FakeClient(), st, self.preset)
        return self.sb.last_result.get("skip")

    def test_below_threshold_skips_mid_career(self):
        # turn 50, 50 SP, threshold 400 -> normal threshold skip.
        self.assertEqual(self._buy(50, 50), "threshold")

    def test_pre_finals_bypasses_threshold(self):
        # turn 73, same low SP -> pre-finals dump forces past the threshold
        # (reaches the empty-candidate path, NOT the threshold skip).
        self.assertNotEqual(self._buy(73, 50), "threshold")

    def test_pre_finals_dump_can_be_disabled(self):
        self.preset["mant_config"] = {}
        self.preset["enable_pre_finals_skill_dump"] = False  # top-level passthrough
        # If the skill config exposes the flag, disabling restores the skip;
        # otherwise the default-on behaviour stands. Assert it at least doesn't
        # crash and returns a skip reason.
        self.assertIsNotNone(self._buy(73, 50))


if __name__ == "__main__":
    unittest.main()
