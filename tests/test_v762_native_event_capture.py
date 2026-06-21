"""Regression tests for v7.6.2 native event-outcome capture.

SweepyCL is an API bot: it already receives chara_info before/after every event
choice, so it records event outcomes from its own runs into the KB — no Frida or
external dumper needed (career_bot/event_outcomes.py: compute_chara_delta /
record_observation). These tests lock in the diff math and the KB merge.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from career_bot import event_outcomes as kb


class ComputeCharaDeltaTests(unittest.TestCase):
    def test_basic_stat_delta(self):
        before = {"speed": 100, "stamina": 50, "vital": 60, "turn": 10, "fans": 1000}
        after = {"speed": 110, "stamina": 56, "vital": 55, "turn": 11, "fans": 1500}
        d = kb.compute_chara_delta(before, after)
        self.assertEqual(d["speed"], 10)
        self.assertEqual(d["stamina"], 6)
        self.assertEqual(d["vital"], -5)
        # run/account state must NOT be treated as a reward
        self.assertNotIn("turn", d)
        self.assertNotIn("fans", d)

    def test_conditions_and_skill_hints(self):
        before = {"speed": 100, "chara_effect_id_array": [1, 2], "skill_tips_array": [{"group_id": 9, "level": 1}]}
        after = {"speed": 100, "chara_effect_id_array": [2, 3], "skill_tips_array": [{"group_id": 9, "level": 2}, {"group_id": 20049, "level": 1}]}
        d = kb.compute_chara_delta(before, after)
        self.assertEqual(d["gained_conditions"], [3])
        self.assertEqual(d["lost_conditions"], [1])
        self.assertEqual(d["gained_skill_hints"]["9"], 1)   # 1 -> 2
        self.assertEqual(d["gained_skill_hints"]["20049"], 1)

    def test_bool_not_treated_as_int(self):
        d = kb.compute_chara_delta({"is_x": False, "speed": 1}, {"is_x": True, "speed": 4})
        self.assertEqual(d.get("speed"), 3)
        self.assertNotIn("is_x", d)

    def test_no_change_is_empty(self):
        self.assertEqual(kb.compute_chara_delta({"speed": 5}, {"speed": 5}), {})


class RecordObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        (Path(self.tmp) / "data").mkdir()
        # seed an empty live KB so project_base resolves to tmp
        (Path(self.tmp) / "data" / "event_outcomes.json").write_text("{}", encoding="utf-8")
        os.environ["UMA_RUNTIME_DIR"] = str(Path(self.tmp) / "uma_runtime")

    def tearDown(self):
        os.environ.pop("UMA_RUNTIME_DIR", None)

    def _kb(self):
        return json.loads((Path(self.tmp) / "data" / "event_outcomes.json").read_text(encoding="utf-8"))

    def test_records_keyed_by_story_id(self):
        res = kb.record_observation(
            self.tmp, story_id="400001", select_index=2, event_name="Test Event",
            before={"speed": 10}, after={"speed": 16},
        )
        self.assertTrue(res["success"])
        data = self._kb()
        self.assertIn("400001", data)
        entry = data["400001"]
        self.assertEqual(entry["source"], kb.NATIVE_SOURCE)
        self.assertEqual(entry["details"]["2"]["speed"], 6)
        self.assertEqual(entry["observations"], 1)
        self.assertIn("speed", entry["outcomes"]["2"])

    def test_merge_keeps_larger_magnitude_and_counts(self):
        kb.record_observation(self.tmp, story_id="x", select_index=1, before={"speed": 0}, after={"speed": 4})
        kb.record_observation(self.tmp, story_id="x", select_index=1, before={"speed": 0}, after={"speed": 9})
        kb.record_observation(self.tmp, story_id="x", select_index=1, before={"speed": 0}, after={"speed": 3})
        entry = self._kb()["x"]
        self.assertEqual(entry["details"]["1"]["speed"], 9)  # extreme kept (dumper-style)
        self.assertEqual(entry["observations"], 3)

    def test_no_delta_is_not_recorded(self):
        res = kb.record_observation(self.tmp, story_id="y", select_index=1, before={"speed": 5}, after={"speed": 5})
        self.assertFalse(res["success"])
        self.assertNotIn("y", self._kb())

    def test_missing_story_id_rejected(self):
        res = kb.record_observation(self.tmp, story_id="", select_index=1, before={"speed": 0}, after={"speed": 5})
        self.assertFalse(res["success"])


if __name__ == "__main__":
    unittest.main()
