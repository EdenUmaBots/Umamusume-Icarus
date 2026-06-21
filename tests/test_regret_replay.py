"""Tests for the counterfactual regret-replay module (Idea #2).

Uses synthetic career-log fixtures shaped like the real career_log_*.json
``turns`` array. Covers both regret passes plus the honest fall-back when a
log carries no candidate scores.
"""
from __future__ import annotations

import unittest

from career_bot import regret_replay as rr


def _train_turn(turn, command_id, candidates=None, state=None):
    """Build a turn whose executed action is a training command."""
    t = {
        "turn": turn,
        "decision_report": {
            "action": "command",
            "payload": {"command_type": 1, "command_id": command_id},
        },
    }
    if candidates is not None:
        t["decision_report"]["training_candidates"] = candidates
    if state is not None:
        t["decision_report"]["state"] = state
    return t


class DecisionRegretTests(unittest.TestCase):
    def test_zero_regret_when_top_option_chosen(self):
        # Chose command 101 (speed), which is also the highest-scored.
        turns = [_train_turn(3, 101, candidates=[
            {"command_id": 101, "name": "Speed", "score": 50.0},
            {"command_id": 105, "name": "Stamina", "score": 30.0},
        ])]
        report = rr.analyze_regret({"turns": turns})
        self.assertTrue(report.has_candidate_data)
        self.assertEqual(report.decision_regret_total, 0.0)

    def test_positive_regret_when_better_option_left(self):
        # Chose 105 (30) when 101 (50) was available -> regret 20.
        turns = [_train_turn(7, 105, candidates=[
            {"command_id": 101, "name": "Speed", "score": 50.0},
            {"command_id": 105, "name": "Stamina", "score": 30.0},
        ])]
        report = rr.analyze_regret({"turns": turns})
        self.assertTrue(report.has_candidate_data)
        self.assertAlmostEqual(report.decision_regret_total, 20.0)
        top = report.top_decision_regret[0]
        self.assertEqual(top.turn, 7)
        self.assertEqual(top.best_id, 101)
        self.assertAlmostEqual(top.regret, 20.0)

    def test_top_n_ordering(self):
        turns = [
            _train_turn(1, 105, candidates=[
                {"command_id": 101, "score": 40.0}, {"command_id": 105, "score": 35.0}]),
            _train_turn(2, 105, candidates=[
                {"command_id": 101, "score": 90.0}, {"command_id": 105, "score": 10.0}]),
        ]
        report = rr.analyze_regret({"turns": turns}, top_n=2)
        # Turn 2 has regret 80, turn 1 has regret 5 -> turn 2 first.
        self.assertEqual([t.turn for t in report.top_decision_regret], [2, 1])
        self.assertAlmostEqual(report.decision_regret_total, 85.0)


class HindsightRegretTests(unittest.TestCase):
    def test_flags_capped_stat_training(self):
        target = {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200}
        # Trained speed at 1300 (over 1200) while stamina is 100 (500 short).
        turns = [_train_turn(40, 101, state={
            "speed": 1300, "stamina": 100, "power": 800, "guts": 600, "wit": 800})]
        report = rr.analyze_regret({"turns": turns}, target_stats=target)
        self.assertEqual(len(report.hindsight_flags), 1)
        flag = report.hindsight_flags[0]
        self.assertEqual(flag.stat, "speed")
        self.assertEqual(flag.neglected_stat, "stamina")
        self.assertEqual(flag.overshoot, 100)
        self.assertEqual(flag.neglected_gap, 500)
        self.assertEqual(flag.wasted, 100)  # min(100, 500)

    def test_no_flag_when_stat_under_target(self):
        target = {"speed": 1200, "stamina": 600, "power": 1200, "guts": 600, "wit": 1200}
        # Speed at 800, still under target -> not wasted.
        turns = [_train_turn(40, 101, state={
            "speed": 800, "stamina": 100, "power": 800, "guts": 600, "wit": 800})]
        report = rr.analyze_regret({"turns": turns}, target_stats=target)
        self.assertEqual(report.hindsight_flags, [])
        self.assertEqual(report.hindsight_wasted_total, 0)

    def test_title_case_target_accepted(self):
        target = {"Speed": 1200, "Stamina": 600, "Power": 1200, "Guts": 600, "Wit": 1200}
        normalized = rr.normalize_target_stats(target)
        self.assertEqual(normalized["speed"], 1200)
        self.assertEqual(normalized["stamina"], 600)


def _trace(turn, reason, candidates):
    return {"turn": turn, "action": "command", "reason": reason,
            "training_candidates": candidates}


class TraceRegretTests(unittest.TestCase):
    def test_decision_regret_from_traces(self):
        # Bot trained Power (0.30) when Speed (0.50) scored higher -> regret 0.20.
        traces = [_trace(7, "Train Power", [
            {"command_id": 101, "name": "Speed", "score": 0.50},
            {"command_id": 102, "name": "Power", "score": 0.30},
        ])]
        report = rr.analyze_regret(trace_rows=traces)
        self.assertTrue(report.has_candidate_data)
        self.assertAlmostEqual(report.decision_regret_total, 0.20, places=6)
        top = report.top_decision_regret[0]
        self.assertEqual(top.chosen_id, 102)
        self.assertEqual(top.best_id, 101)

    def test_zero_regret_when_best_trained(self):
        traces = [_trace(3, "Train Speed", [
            {"command_id": 101, "name": "Speed", "score": 0.50},
            {"command_id": 102, "name": "Power", "score": 0.30},
        ])]
        report = rr.analyze_regret(trace_rows=traces)
        self.assertEqual(report.decision_regret_total, 0.0)

    def test_non_command_rows_skipped(self):
        traces = [
            {"turn": 5, "action": "race", "reason": "Race G1", "training_candidates": []},
            _trace(6, "Rest", [{"command_id": 101, "name": "Speed", "score": 0.5}]),
        ]
        report = rr.analyze_regret(trace_rows=traces)
        self.assertFalse(report.has_candidate_data)

    def test_traces_take_priority_over_log(self):
        # Even with embedded log candidates, trace_rows win.
        log = {"turns": [_train_turn(7, 105, candidates=[
            {"command_id": 101, "score": 99.0}, {"command_id": 105, "score": 0.0}])]}
        traces = [_trace(7, "Train Stamina", [
            {"command_id": 101, "name": "Speed", "score": 0.40},
            {"command_id": 105, "name": "Stamina", "score": 0.35}])]
        report = rr.analyze_regret(log, trace_rows=traces)
        # Uses the trace scores (regret 0.05), not the log's (99.0).
        self.assertAlmostEqual(report.decision_regret_total, 0.05, places=6)


class FallbackTests(unittest.TestCase):
    def test_no_candidate_data_is_honest(self):
        # No training_candidates on any turn -> decision regret unavailable.
        turns = [_train_turn(5, 101, state={
            "speed": 700, "stamina": 300, "power": 500, "guts": 400, "wit": 600})]
        report = rr.analyze_regret({"turns": turns})
        self.assertFalse(report.has_candidate_data)
        self.assertTrue(any("decision-regret" in n.lower() for n in report.notes))

    def test_empty_log(self):
        report = rr.analyze_regret({"turns": []})
        self.assertFalse(report.has_candidate_data)
        self.assertEqual(report.hindsight_wasted_total, 0)

    def test_summary_lines_render(self):
        turns = [_train_turn(7, 105, candidates=[
            {"command_id": 101, "name": "Speed", "score": 50.0},
            {"command_id": 105, "name": "Stamina", "score": 30.0},
        ], state={"speed": 100, "stamina": 100, "power": 100, "guts": 100, "wit": 100})]
        report = rr.analyze_regret({"turns": turns})
        lines = rr.regret_summary_lines(report)
        self.assertTrue(any("Decision regret" in l for l in lines))
        self.assertIsInstance(rr.render_report(report), str)


if __name__ == "__main__":
    unittest.main()
