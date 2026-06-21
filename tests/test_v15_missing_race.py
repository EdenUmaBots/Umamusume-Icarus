"""v1.5: missing-race substitute.

When the smart solver planned a race for this turn but the exact program is not
in the live race list (calendar drift), the planner now races the best AVAILABLE
aptitude-passing race from the live list -- instead of re-solving the whole
remaining schedule, which eroded the plan ~1 race per "missing" event (24/run)
and was the main reason executed races stalled ~10 below the plan.
"""
import tempfile
import unittest
from pathlib import Path

from career_bot.races import RacePlanner


def _planner():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    p = RacePlanner(tmp)
    p.program = {
        100: {"name": "Live G3", "grade": "G3", "distance": 1600, "ground": 1, "fans": 10000},
        200: {"name": "Live G1", "grade": "G1", "distance": 1600, "ground": 1, "fans": 20000},
    }
    # The solver planned race id 999 for turn 30, mapping to program 999.
    p.meta = {999: {"turn": 30, "program_id": 999, "name": "Planned (missing)"}}
    # choose() re-solves the live schedule first; in this lightweight harness
    # there is no solver data, so stub it out to preserve the hand-built plan.
    p._replan_smart_schedule = lambda *a, **k: None
    return p


def _state(available, turn=30):
    return {"data": {
        "chara_info": {
            "turn": turn, "scenario_id": 4, "fans": 5000,
            "proper_distance_short": 8, "proper_distance_mile": 8,
            "proper_distance_middle": 8, "proper_distance_long": 8,
            "proper_ground_turf": 8, "proper_ground_dirt": 8,
        },
        "home_info": {"command_info_array": [
            {"command_type": 4, "command_id": 401, "is_enable": 1}]},
        "race_condition_array": [{"program_id": pid} for pid in available],
        "free_data_set": {"rival_race_info_array": []},
    }}


class MissingRaceSubstituteTests(unittest.TestCase):
    def test_substitutes_live_race_when_planned_is_missing(self):
        p = _planner()
        # 999 is planned but NOT in the live list; 100/200 are available.
        st = _state(available=[100, 200], turn=30)
        preset = {"extra_race_list": [999], "extra_race_list_source": "smart",
                  "mant_config": {}}
        chosen = p.choose(st, preset)
        self.assertIn(chosen, (100, 200), "should race a live race, not drop to train")

    def test_disabled_falls_back_to_train(self):
        p = _planner()
        st = _state(available=[100, 200], turn=30)
        preset = {"extra_race_list": [999], "extra_race_list_source": "smart",
                  "mant_config": {"enable_missing_race_substitute": False}}
        chosen = p.choose(st, preset)
        # With the substitute off and the planned race missing, smart mode does
        # not race the live list -> returns 0 (train).
        self.assertEqual(chosen, 0)

    def test_no_substitute_when_no_live_race_available(self):
        p = _planner()
        st = _state(available=[], turn=30)  # nothing available
        preset = {"extra_race_list": [999], "extra_race_list_source": "smart",
                  "mant_config": {}}
        self.assertEqual(p.choose(st, preset), 0)

    def test_manual_strict_by_default_trains_on_missing(self):
        p = _planner()
        st = _state(available=[100, 200], turn=30)
        preset = {"extra_race_list": [999], "extra_race_list_source": "manual",
                  "mant_config": {}}
        # Manual is strict: a picked race that is not offered -> train, no sub.
        self.assertEqual(p.choose(st, preset), 0)

    def test_manual_opt_in_substitutes_when_enabled(self):
        p = _planner()
        st = _state(available=[100, 200], turn=30)
        preset = {"extra_race_list": [999], "extra_race_list_source": "manual",
                  "mant_config": {"manual_missing_race_substitute": True}}
        # With the opt-in flag, a missing picked race -> best live race.
        self.assertIn(p.choose(st, preset), (100, 200))


if __name__ == "__main__":
    unittest.main()
