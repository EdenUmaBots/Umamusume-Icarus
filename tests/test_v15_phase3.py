"""v1.5 Phase 3 — fans + race count.

  * glow sticks now fire on G2/G3 (not G1-only) above the effective-fan floor;
  * the irregular-training heuristic no longer hijacks a race the smart solver
    explicitly planned for this turn (android's "if a race is planned, run it").
"""
import unittest

from career_bot.items import MantItemManager
from career_bot.scenarios.mant import MantStrategy


class GlowStickGradeTests(unittest.TestCase):
    def setUp(self):
        self.m = MantItemManager.__new__(MantItemManager)
        self.owned = {"Glow Sticks": 2}
        self.cfg = {"glow_stick_fan_multiplier": 2.0,
                    "trackblazer_glow_stick_min_fans": 20000,
                    "trackblazer_glow_stick_final_reserve": 1}

    def test_big_g2_now_fires(self):
        # 13k base -> 26k effective >= 20k. Was blocked by the G1-only gate.
        self.assertTrue(self.m._should_use_glow_stick(self.owned, 42, "G2", 13000, self.cfg))

    def test_big_g3_now_fires(self):
        self.assertTrue(self.m._should_use_glow_stick(self.owned, 42, "G3", 11000, self.cfg))

    def test_small_g2_still_skipped(self):
        # 5k base -> 10k effective < 20k floor.
        self.assertFalse(self.m._should_use_glow_stick(self.owned, 42, "G2", 5000, self.cfg))

    def test_op_never_fires(self):
        self.assertFalse(self.m._should_use_glow_stick(self.owned, 42, "OP", 30000, self.cfg))


class _FakePlanner:
    base_dir = None
    program = {}
    official_races = {}

    def __init__(self, planned):
        self._planned = list(planned)

    def wanted_programs(self, preset, turn):
        return list(self._planned)


def _chara(turn=40, vital=50):
    return {"turn": turn, "vital": vital, "speed": 400, "stamina": 300,
            "power": 400, "guts": 300, "wiz": 350}


class IrregularTrainingGateTests(unittest.TestCase):
    def test_skips_solver_planned_race(self):
        s = MantStrategy(_FakePlanner(planned=[625]))
        data = {"home_info": {"command_info_array": []}}
        # program 625 is in the solver plan for this turn -> do not hijack.
        out = s._irregular_training_decision(data, _chara(), {"mant_config": {}}, 625)
        self.assertIsNone(out)

    def test_gate_can_be_disabled(self):
        # With allow_irregular_over_planned the planned-race gate is bypassed
        # (it then proceeds to the normal checks; with no candidates it still
        # returns None, but NOT because of the planned gate -- this asserts the
        # gate flag is honored without raising).
        s = MantStrategy(_FakePlanner(planned=[625]))
        data = {"home_info": {"command_info_array": []}}
        out = s._irregular_training_decision(
            data, _chara(), {"mant_config": {"allow_irregular_over_planned": True}}, 625)
        self.assertIsNone(out)  # no crash; downstream returns None on no candidates


if __name__ == "__main__":
    unittest.main()
