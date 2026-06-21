"""v1.5: in-game agenda (reserved race) + debut-only free retries.

- In-game agenda: the game exposes the user's manually-reserved race as
  chara_info.reserve_race_program_id. With use_ingame_agenda on, the planner
  races it when it's available, overriding the solver.
- Debut-only free retries: _is_debut_race detects the Make Debut / Maiden race
  by name so free continues can be reserved for it.
"""
import tempfile
import unittest
from pathlib import Path

from career_bot.races import RacePlanner
from career_bot.runner import CareerRunner


def _planner():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    p = RacePlanner(tmp)
    p.program = {
        100: {"name": "Make Debut", "grade": "Pre-OP", "distance": 1600, "ground": 1, "fans": 1000},
        200: {"name": "Tokyo Cup G1", "grade": "G1", "distance": 1600, "ground": 1, "fans": 20000},
        300: {"name": "Mile Trophy", "grade": "G2", "distance": 1600, "ground": 1, "fans": 15000},
    }
    p._replan_smart_schedule = lambda *a, **k: None
    return p


def _state(available, turn=30, reserved=0):
    return {"data": {
        "chara_info": {
            "turn": turn, "scenario_id": 4, "fans": 5000,
            "reserve_race_program_id": reserved,
            "proper_distance_short": 8, "proper_distance_mile": 8,
            "proper_distance_middle": 8, "proper_distance_long": 8,
            "proper_ground_turf": 8, "proper_ground_dirt": 8,
        },
        "home_info": {"command_info_array": [
            {"command_type": 4, "command_id": 401, "is_enable": 1}]},
        "race_condition_array": [{"program_id": pid} for pid in available],
        "free_data_set": {"rival_race_info_array": []},
    }}


class InGameAgendaTests(unittest.TestCase):
    def test_reserved_race_is_run_when_enabled(self):
        p = _planner()
        st = _state(available=[200, 300], turn=30, reserved=300)
        preset = {"extra_race_list_source": "smart",
                  "mant_config": {"use_ingame_agenda": True}}
        # Reserved 300 (a G2) is honored even though 200 (G1) scores higher.
        self.assertEqual(p.choose(st, preset), 300)

    def test_reservation_ignored_when_option_off(self):
        p = _planner()
        st = _state(available=[200, 300], turn=30, reserved=300)
        preset = {"extra_race_list_source": "smart", "mant_config": {}}
        # Option off -> the reservation is not forced.
        self.assertNotEqual(p.choose(st, preset), 300)

    def test_reservation_not_available_this_turn_falls_through(self):
        p = _planner()
        st = _state(available=[200, 300], turn=30, reserved=999)  # 999 not offered
        preset = {"extra_race_list_source": "smart",
                  "mant_config": {"use_ingame_agenda": True}}
        self.assertNotEqual(p.choose(st, preset), 999)


class DebutRaceDetectionTests(unittest.TestCase):
    def _runner(self):
        r = CareerRunner.__new__(CareerRunner)
        r.race_planner = _planner()
        return r

    def test_detects_make_debut(self):
        self.assertTrue(self._runner()._is_debut_race(100))

    def test_non_debut_race_is_false(self):
        r = self._runner()
        self.assertFalse(r._is_debut_race(200))
        self.assertFalse(r._is_debut_race(300))

    def test_missing_program_safe(self):
        self.assertFalse(self._runner()._is_debut_race(0))


if __name__ == "__main__":
    unittest.main()
