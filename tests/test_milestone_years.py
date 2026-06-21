"""v1.5: milestone target down-scaling defaults OFF (full targets all career),
matching the real Android scorer, which measures stat completion against the
FULL per-distance target every turn and lets its ratio-bucket multipliers create
natural pacing.  The v1.4 33%/66% scaling back-loaded stats and lost winnable
Classic/Senior races, so it is now opt-in via the milestone-pct keys.
"""
import unittest

from career_bot.scenarios.mant import MantStrategy

ROW = [1200, 600, 1000, 500, 1000]  # mile targets (speed first)


def _targets(turn, mant_extra):
    s = MantStrategy()
    cfg = {"preferred_distance": "mile", "stat_targets_by_distance": {"mile": list(ROW)}}
    cfg.update(mant_extra)
    return s._training_targets({"mant_config": cfg}, {"turn": turn})


class MilestoneYearTests(unittest.TestCase):
    def test_default_is_full_targets_all_career(self):
        # No milestone keys set -> full targets in Classic, Senior, and finals,
        # like the Android bot (no year scaling).
        self.assertEqual(_targets(40, {})[0], 1200)   # Classic
        self.assertEqual(_targets(60, {})[0], 1200)   # Senior
        self.assertEqual(_targets(75, {})[0], 1200)   # Finals

    def test_classic_scaling_is_opt_in(self):
        self.assertEqual(_targets(40, {"classic_year_milestone_pct": 33})[0], int(1200 * 0.33))

    def test_senior_scaling_is_opt_in(self):
        self.assertEqual(_targets(60, {"senior_year_milestone_pct": 66})[0], int(1200 * 0.66))

    def test_finals_always_full(self):
        self.assertEqual(_targets(75, {"classic_year_milestone_pct": 33,
                                       "senior_year_milestone_pct": 66})[0], 1200)

    def test_legacy_keys_still_honored_when_set(self):
        # Old junior(33) -> Classic slot, old classic(66) -> Senior slot.
        extra = {"junior_milestone_pct": 33, "classic_milestone_pct": 66}
        self.assertEqual(_targets(40, extra)[0], int(1200 * 0.33))   # Classic
        self.assertEqual(_targets(60, extra)[0], int(1200 * 0.66))   # Senior


if __name__ == "__main__":
    unittest.main()
