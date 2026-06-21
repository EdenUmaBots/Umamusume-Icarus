"""Regression tests for v6.7.12:

  1. Mandatory race loss no longer crashes the runner.  Finale races
     (turn >= 73) complete the career gracefully; non-finale mandatory
     losses set a clean stop reason instead of raising.

  2. Mandatory races may use paid clocks even when burn_clocks is off
     (a finale loss is catastrophic).  Opt out with
     disable_mandatory_race_clocks.

  3. Stat-target fallback: when the preset's stat_targets_by_distance
     doesn't cover the trainee's race distance, the built-in
     per-distance defaults are used (Medium 800 / Long 1000 stamina)
     instead of the meaningless 9999 sentinel.  This was the cause of
     trainees under-building stamina for Medium/Long races.
"""
import sys
import threading
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("msgpack", MagicMock())


# --- 1. Mandatory clock rescue -------------------------------------------

class MandatoryClockRescueTests(unittest.TestCase):
    """v6.7.12: a mandatory race may spend paid clocks to avoid a
    catastrophic career-ending loss, even when burn_clocks is off."""

    def _runner(self, *, burn_clocks):
        from career_bot.runner import CareerRunner
        r = CareerRunner.__new__(CareerRunner)
        r.burn_clocks = burn_clocks
        r._race_grade_for_retry = lambda program_id: "G1"
        return r

    def test_mandatory_race_uses_paid_clocks_with_burn_off(self):
        """The user's exact crash scenario: burn_clocks=False, finale
        race lost, 5 paid clocks available.  v6.7.12: the policy must
        now ENABLE the retry (paid-clock rescue) instead of leaving
        the loss to crash the career."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            {"mant_config": {}}, program_id=2510, turn=78, attempts=0,
            free_clocks_available=0,  # no free clocks, but...
            is_mandatory=True,        # mandatory race
        )
        self.assertTrue(policy["enabled"], "mandatory race must enable paid-clock rescue")
        self.assertTrue(policy.get("mandatory_clock_rescue"))
        self.assertEqual(policy["disabled_reason"], "paid_clocks_via_mandatory_rescue")

    def test_optional_graded_race_retries_by_default(self):
        """v1.5: graded optional extra races now retry by default (android
        parity), decoupled from the Burn Clocks toggle, to lift win rate."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            {"mant_config": {}}, program_id=1234, turn=40, attempts=0,
            free_clocks_available=0,
            is_mandatory=False,
        )
        self.assertTrue(policy["enabled"])
        self.assertTrue(policy.get("extra_race_retry"))

    def test_optional_race_blocked_when_extra_retry_disabled(self):
        """Setting retry_extra_races=false restores the old burn_clocks-gated
        behaviour: an optional race with burn off and no free clocks is blocked."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            {"mant_config": {"retry_extra_races": False}}, program_id=1234, turn=40,
            attempts=0, free_clocks_available=0, is_mandatory=False,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "burn_clocks_disabled_by_user")

    def test_mandatory_rescue_can_be_disabled(self):
        """Users who never want paid clocks spent can opt out via
        disable_mandatory_race_clocks."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            {"mant_config": {"disable_mandatory_race_clocks": True}},
            program_id=2510, turn=78, attempts=0,
            free_clocks_available=0, is_mandatory=True,
        )
        self.assertFalse(policy["enabled"])

    def test_mandatory_race_bypasses_grade_filter(self):
        """A mandatory race must be retried regardless of its grade,
        even if the preset restricts retries to specific grades."""
        runner = self._runner(burn_clocks=True)
        runner._race_grade_for_retry = lambda program_id: "OP"  # not in default G1/G2/G3
        policy = runner._race_retry_policy(
            {"mant_config": {"retry_race_grades": ["G1"]}},
            program_id=2510, turn=78, attempts=0,
            free_clocks_available=0, is_mandatory=True,
        )
        self.assertTrue(policy["enabled"], "mandatory race bypasses the grade filter")

    def test_mandatory_rescue_respects_max_retries(self):
        """Even mandatory rescue stops at the per-race retry cap."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            {"mant_config": {"max_retries_per_race": 5}},
            program_id=2510, turn=78, attempts=5,
            free_clocks_available=0, is_mandatory=True,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "max_retries_reached")


# --- 2. Stat-target fallback ---------------------------------------------

class StatTargetFallbackTests(unittest.TestCase):
    """v6.7.12: when stat_targets_by_distance doesn't cover the
    trainee's race distance, the built-in per-distance defaults are
    used instead of the 9999 sentinel."""

    def setUp(self):
        from career_bot.scenarios.mant import MantStrategy
        self.strat = MantStrategy()

    def _chara(self, *, turn=60, middle_apt=7, mile_apt=5, long_apt=4, short_apt=2):
        return {
            "turn": turn,
            "proper_distance_short": short_apt,
            "proper_distance_mile": mile_apt,
            "proper_distance_middle": middle_apt,
            "proper_distance_long": long_apt,
        }

    def test_middle_distance_uses_default_when_only_mile_set(self):
        """The user's exact bug: preset sets only 'mile' targets, but
        the trainee's best distance is Middle.  v6.7.12: must fall back
        to the Middle default (stamina 800), NOT the 9999 sentinel."""
        preset = {
            "mant_config": {
                "stat_targets_by_distance": {"mile": [1200, 700, 1100, 400, 1000]},
                "preferred_distance": "auto",
            },
            "expect_attribute": [9999, 9999, 9999, 9999, 9999],
        }
        # Trainee's best aptitude is Middle (middle_apt=7)
        targets = self.strat._training_targets(preset, self._chara(turn=60, middle_apt=7))
        # Middle default is [1200, 800, 1000, 600, 900].  Stamina (index 1)
        # must be the default 800, NOT 9999.
        self.assertEqual(targets[1], 800, "Middle stamina target must come from defaults, not 9999")
        self.assertNotEqual(targets[1], 9999)

    def test_long_distance_uses_default_when_only_mile_set(self):
        """Same fallback for Long-distance trainees."""
        preset = {
            "mant_config": {
                "stat_targets_by_distance": {"mile": [1200, 700, 1100, 400, 1000]},
                "preferred_distance": "auto",
            },
            "expect_attribute": [9999, 9999, 9999, 9999, 9999],
        }
        targets = self.strat._training_targets(preset, self._chara(turn=60, long_apt=8, middle_apt=5))
        # Long default is [1200, 1000, 900, 700, 900].  Stamina must be 1000.
        self.assertEqual(targets[1], 1000, "Long stamina target must come from defaults")

    def test_explicit_distance_target_still_wins(self):
        """When the preset DOES specify the trainee's distance, that
        explicit value is used (not the default)."""
        preset = {
            "mant_config": {
                "stat_targets_by_distance": {
                    "mile": [1200, 700, 1100, 400, 1000],
                    "medium": [1150, 850, 1050, 400, 1000],  # explicit Medium
                },
                "preferred_distance": "auto",
            },
            "expect_attribute": [9999, 9999, 9999, 9999, 9999],
        }
        targets = self.strat._training_targets(preset, self._chara(turn=60, middle_apt=7))
        # Should use the explicit Medium stamina 850, not the default 800
        self.assertEqual(targets[1], 850, "explicit Medium target must win over default")

    def test_senior_year_targets_not_scaled_down(self):
        """Senior-year (turn > 48) targets are used at full value (no
        milestone scaling)."""
        preset = {
            "mant_config": {
                "stat_targets_by_distance": {"middle": [1200, 800, 1000, 600, 900]},
                "preferred_distance": "auto",
            },
        }
        targets = self.strat._training_targets(preset, self._chara(turn=60, middle_apt=7))
        # Senior year: full stamina target
        self.assertEqual(targets[1], 800)

    def test_junior_year_targets_scaled(self):
        """Junior-year (turn <= 24) targets are scaled to ~33%."""
        preset = {
            "mant_config": {
                "stat_targets_by_distance": {"middle": [1200, 800, 1000, 600, 900]},
                "preferred_distance": "auto",
                "junior_milestone_pct": 33,
            },
        }
        targets = self.strat._training_targets(preset, self._chara(turn=10, middle_apt=7))
        # 800 * 0.33 = 264
        self.assertEqual(targets[1], int(800 * 0.33))


if __name__ == "__main__":
    unittest.main()
