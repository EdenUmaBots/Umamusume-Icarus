"""Tests for the cross-bot career benchmark harness (Idea #1)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import benchmark as bm  # noqa: E402


def _icarus_log():
    """A small but Icarus-shaped career log."""
    return {
        "preset_name": "Test",
        "scenario_id": 1,
        "final_turn": 4,
        "started_at": "2026-06-18T00:00:00",
        "ended_at": "2026-06-18T01:00:00",  # 1 hour
        "runner_status": {
            "final_stats": {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200},
            "final_fans": 120000,
            "final_rating": 17000,
            "final_rank": "SS",
            "final_chara": {"card_id": 100601, "stats": {}},
            "race_results": [
                {"turn": 2, "name": "Race A", "grade": "G1", "rank": 1, "fans": 8000},
                {"turn": 3, "name": "Race B", "grade": "G1", "rank": 4, "fans": 2000},
            ],
        },
        "turns": [
            {"turn": 1, "decision_report": {"action": "command", "payload": {"command_type": 1, "command_id": 101}},
             "api_calls": [{"direction": "RES", "data": {"response": {"chara_info": {
                 "card_id": 100601, "trained_chara_name": "Oguri Cap"}}}}]},
            {"turn": 2, "decision_report": {"action": "command", "payload": {"command_type": 7, "command_id": 701}}},
            {"turn": 3, "decision_report": {"action": "race", "payload": {"program_id": 99901}}},
            {"turn": 4, "decision_report": {"action": "command", "payload": {"command_type": 1, "command_id": 105}}},
        ],
    }


def _foreign_log():
    return {
        "trainee_name": "Oguri Cap",
        "scenario_id": 1,
        "final_turn": 4,
        "runtime_seconds": 7200,  # 2 hours
        "final_stats": {"speed": 800, "stamina": 400, "power": 700, "guts": 400, "wit": 600},
        "final_fans": 60000,
        "final_rating": 9000,
        "final_rank": "A",
        "races": [
            {"turn": 2, "name": "Race A", "grade": "G1", "rank": 3},
            {"turn": 3, "name": "Race B", "grade": "G1", "rank": 1},
        ],
        "turns": [
            {"turn": 1, "action": "train", "stat": "speed"},
            {"turn": 2, "action": "rest"},
            {"turn": 3, "action": "race"},
            {"turn": 4, "action": "train", "stat": "stamina"},
        ],
    }


class DetectionTests(unittest.TestCase):
    def test_icarus_detected(self):
        self.assertTrue(bm.is_icarus_log(_icarus_log()))

    def test_foreign_not_icarus(self):
        self.assertFalse(bm.is_icarus_log(_foreign_log()))


class IngestTests(unittest.TestCase):
    def test_ingest_icarus(self):
        run = bm.ingest_icarus(_icarus_log(), "log1", REPO_ROOT)
        self.assertEqual(run.source, "icarus")
        self.assertEqual(run.trainee_name, "Oguri Cap")
        self.assertEqual(run.card_id, 100601)
        self.assertEqual(run.final_stats["speed"], 1200)
        self.assertEqual(len(run.races), 2)
        self.assertEqual(run.runtime_seconds, 3600.0)
        # turn 1 train(speed), 2 rest, 3 race, 4 train(stamina)
        kinds = [t["action"] for t in run.turns]
        self.assertEqual(kinds, ["train", "rest", "race", "train"])

    def test_ingest_foreign(self):
        run = bm.ingest_foreign(_foreign_log(), "android1", REPO_ROOT, source="android")
        self.assertEqual(run.source, "android")
        self.assertEqual(run.final_stats["wit"], 600)
        self.assertEqual(run.runtime_seconds, 7200)
        self.assertEqual(len(run.races), 2)


class ScoreTests(unittest.TestCase):
    def test_perfect_stats_full_achievement(self):
        run = bm.ingest_icarus(_icarus_log(), "log1", REPO_ROOT)
        # final stats equal the default target build -> 100%.
        run.target_stats = {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200}
        m = bm.score_run(run)
        self.assertEqual(m["stat_achievement"], 100.0)
        self.assertEqual(m["race_win_rate"], 50.0)  # 1 of 2
        self.assertEqual(m["fans_per_hour"], 120000.0)  # 120k over 1h
        # 1 rest of 4 turns -> 75% energy efficiency.
        self.assertEqual(m["energy_efficiency"], 75.0)

    def test_composite_present_and_bounded(self):
        run = bm.ingest_foreign(_foreign_log(), "android1", REPO_ROOT)
        m = bm.score_run(run)
        self.assertGreaterEqual(m["composite"], 0.0)
        self.assertLessEqual(m["composite"], 100.0)

    def test_icarus_outranks_weaker_foreign(self):
        strong = bm.ingest_icarus(_icarus_log(), "icarus", REPO_ROOT)
        strong.target_stats = {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200}
        weak = bm.ingest_foreign(_foreign_log(), "android", REPO_ROOT)
        weak.target_stats = {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200}
        self.assertGreater(bm.score_run(strong)["composite"], bm.score_run(weak)["composite"])


class EndToEndTests(unittest.TestCase):
    def test_main_runs_on_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ic = d / "career_log_test.json"
            ic.write_text(json.dumps(_icarus_log()), encoding="utf-8")
            fo = d / "android.json"
            fo.write_text(json.dumps(_foreign_log()), encoding="utf-8")
            csv_out = d / "out.csv"
            rc = bm.main([f"icarus={ic}", f"android={fo}", "--csv", str(csv_out)])
            self.assertEqual(rc, 0)
            self.assertTrue(csv_out.exists())
            lines = csv_out.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)  # header + 2 runs

    def test_auto_detect_source(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ic = d / "career_log_auto.json"
            ic.write_text(json.dumps(_icarus_log()), encoding="utf-8")
            run = bm.load_run(ic, "auto", REPO_ROOT)
            self.assertEqual(run.source, "icarus")

    def test_decision_regret_from_adjacent_traces(self):
        # Lay out bot_logs/ + decision_traces/ like the real runtime; the log's
        # run_id must match the trace filename.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "bot_logs").mkdir()
            (d / "decision_traces").mkdir()
            log = _icarus_log()
            log["runtime_settings"] = {"run_id": "run123"}
            log_path = d / "bot_logs" / "career_log_run.json"
            log_path.write_text(json.dumps(log), encoding="utf-8")
            traces = [
                {"turn": 1, "action": "command", "reason": "Train Power",
                 "training_candidates": [
                     {"command_id": 101, "name": "Speed", "score": 0.50},
                     {"command_id": 102, "name": "Power", "score": 0.30}]},
            ]
            (d / "decision_traces" / "run123.jsonl").write_text(
                "\n".join(json.dumps(t) for t in traces), encoding="utf-8")
            run = bm.load_run(log_path, "icarus", REPO_ROOT)
            self.assertEqual(len(run.trace_rows), 1)
            m = bm.score_run(run)
            self.assertIsNotNone(m["decision_regret_mean"])
            self.assertAlmostEqual(m["decision_regret_mean"], 0.20, places=2)


if __name__ == "__main__":
    unittest.main()
