"""v1.5: mood floor (android parity, corrected).

Android recovers mood whenever it slides to NORMAL or below, on any
workable-energy non-camp turn, regardless of the available training -- because
Great mood multiplies every future training AND race.  The first attempt gated
this on a best_score ceiling that a rainbow always cleared, so mood was never
recovered and the trainee ground both summer camps at Bad mood.  Corrected:
recover at/below the floor (NORMAL=3); push to Great on the pre-camp turns.
"""
import unittest

from career_bot.scenarios.mant import MantStrategy

RECREATION = {"command_type": 3, "command_id": 0, "is_enable": 1}


class MoodFloorTests(unittest.TestCase):
    def setUp(self):
        self.s = MantStrategy()
        self.preset = {"mant_config": {}}

    def _rec(self, motivation, vital, best_score=0.7, turn=30):
        return self.s._should_recreate(RECREATION, self.preset, turn, motivation, vital, best_score)

    def test_recovers_at_normal_even_with_strong_training(self):
        # mood NORMAL(3), healthy energy, a strong rainbow available (0.7) ->
        # still recover (the old ceiling bug would have skipped this).
        self.assertTrue(self._rec(motivation=3, vital=80, best_score=0.7))

    def test_recovers_at_bad(self):
        self.assertTrue(self._rec(motivation=2, vital=80))

    def test_good_mood_not_recovered_generally(self):
        # mood GOOD(4) is acceptable outside the pre-camp window.
        self.assertFalse(self._rec(motivation=4, vital=80))

    def test_great_not_recovered(self):
        self.assertFalse(self._rec(motivation=5, vital=80))

    def test_not_recovered_when_energy_too_low(self):
        self.assertFalse(self._rec(motivation=3, vital=40))

    def test_pre_camp_pushes_to_great(self):
        # On the pre-camp turn, GOOD(4) IS recovered (enter camp at Great).
        self.assertTrue(self._rec(motivation=4, vital=80, turn=35))
        self.assertTrue(self._rec(motivation=4, vital=80, turn=59))

    def test_not_during_summer_camp(self):
        self.assertFalse(self._rec(motivation=2, vital=80, turn=37))

    def test_can_be_disabled(self):
        self.preset = {"mant_config": {"enable_keep_great_mood": False}}
        self.assertFalse(self._rec(motivation=2, vital=80))


if __name__ == "__main__":
    unittest.main()
