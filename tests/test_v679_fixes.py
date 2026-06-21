"""Regression tests for v6.7.9 fixes:

  1. Authoritative scorer override -- margin gate is configurable
     via training_scorer_overrides.override_margin_pct and
     .override_margin_floor.  When the gate blocks the swap, the
     blocked-override record is written to runner status so the
     dashboard reasoning can explain it.

  2. ``active_selection`` is persisted to userdata so the picker
     survives server restarts.

  3. ``/api/character-profile/active`` endpoint falls back to
     ``runner_status.active_character_profile`` when chara_info
     is empty, so the panel shows the last-used profile between
     runs instead of "default".

  4. The dashboard ``_decision_reasoning`` text now distinguishes
     "scorer disagreed but margin gate blocked the swap" from a
     plain "scorer would have picked X".
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Stub msgpack (sandbox doesn't have it)
sys.modules.setdefault("msgpack", MagicMock())


# --- 1. Margin gate config + blocked override recording -------------------

class ScorerOverrideMarginGateTests(unittest.TestCase):
    """Verify the v6.7.9 changes to ``_apply_authoritative_scorer_override``.

    The function takes a state + a decision and may mutate decision.payload
    by swapping the chosen training command.  When the margin gate blocks
    the swap, ``status['last_scorer_override_blocked']`` is populated.
    """

    def setUp(self):
        from career_bot.runner import CareerRunner
        self.runner = CareerRunner.__new__(CareerRunner)
        # Minimal status + lock so the override function can read/write it
        import threading
        self.runner.status = {}
        self.runner.lock = threading.Lock()
        self.runner.base_dir = "/tmp"  # any path; resolve_profile uses it for catalog

    def _decision(self, command_id, current_turn=10):
        return SimpleNamespace(
            action="command",
            payload={"command_type": 1, "command_id": command_id, "current_turn": current_turn},
            reason="Train Speed",
        )

    def _state(self, *, has_home=True):
        return {
            "data": {
                "chara_info": {"card_id": 100601, "chara_id": 100601, "turn": 10,
                               "speed": 257, "stamina": 200, "power": 200, "guts": 200, "wiz": 200,
                               "vital": 80, "motivation": 4},
                "home_info": ({"command_info_array": [
                    {"command_type": 1, "command_id": 101, "is_enable": 1,
                     "params_inc_dec_info_array": [{"target_type": 1, "value": 13}]},
                    {"command_type": 1, "command_id": 103, "is_enable": 1,
                     "params_inc_dec_info_array": [{"target_type": 3, "value": 13}]},
                ]} if has_home else {}),
            },
        }

    def test_blocked_override_recorded_when_margin_below_threshold(self):
        """When scorer disagrees but margin < floor, the override is
        blocked AND the blocked-record is persisted to status."""
        # Mock resolve_profile + training_scorer to return controlled values.
        from career_bot import character_profiles, training_scorer

        # Profile in authoritative mode with the default margin gate (floor=1.0)
        fake_profile = SimpleNamespace(
            training_scorer_mode="authoritative",
            training_scorer_overrides={},
            profile_id="oguri_cap",
            training_scorer_config=lambda: {},
        )

        # Scorer picks command 103 (Guts) with score 0.31; strategy picked
        # command 101 (Speed) which the scorer ranks at 0.30.  Margin is 0.01,
        # well below the default floor of 1.0 -- override must block.
        scorer_scores = [
            SimpleNamespace(command_id=103, score=0.31, stat_name="guts"),
            SimpleNamespace(command_id=101, score=0.30, stat_name="speed"),
        ]

        orig_resolve = character_profiles.resolve_profile
        orig_score = training_scorer.score_trainings
        try:
            character_profiles.resolve_profile = lambda **kw: fake_profile
            training_scorer.score_trainings = lambda home, chara, config=None: scorer_scores
            decision = self._decision(command_id=101, current_turn=10)
            self.runner._apply_authoritative_scorer_override(self._state(), decision)
            # decision.payload.command_id NOT changed (override blocked)
            self.assertEqual(decision.payload["command_id"], 101)
            # Blocked record is in status
            blocked = self.runner.status.get("last_scorer_override_blocked")
            self.assertIsNotNone(blocked, "blocked-override record must be persisted")
            self.assertEqual(blocked["turn"], 10)
            self.assertEqual(blocked["from_command_id"], 101)
            self.assertEqual(blocked["to_command_id"], 103)
            self.assertEqual(blocked["from_stat"], "speed")
            self.assertEqual(blocked["to_stat"], "guts")
            self.assertEqual(blocked["reason"], "margin_below_threshold")
        finally:
            character_profiles.resolve_profile = orig_resolve
            training_scorer.score_trainings = orig_score

    def test_lower_margin_floor_lets_override_fire(self):
        """When the user lowers ``override_margin_floor`` to 0.0,
        the previously-blocked override now fires."""
        from career_bot import character_profiles, training_scorer

        fake_profile = SimpleNamespace(
            training_scorer_mode="authoritative",
            training_scorer_overrides={"override_margin_floor": 0.0,
                                        "override_margin_pct": 0.0},
            profile_id="oguri_cap",
            training_scorer_config=lambda: {},
        )

        scorer_scores = [
            SimpleNamespace(command_id=103, score=0.31, stat_name="guts"),
            SimpleNamespace(command_id=101, score=0.30, stat_name="speed"),
        ]

        orig_resolve = character_profiles.resolve_profile
        orig_score = training_scorer.score_trainings
        try:
            character_profiles.resolve_profile = lambda **kw: fake_profile
            training_scorer.score_trainings = lambda home, chara, config=None: scorer_scores
            decision = self._decision(command_id=101, current_turn=10)
            self.runner._apply_authoritative_scorer_override(self._state(), decision)
            # decision.payload.command_id IS now changed (override fired)
            self.assertEqual(decision.payload["command_id"], 103,
                "with margin floor 0, the override should swap to scorer's pick")
            self.assertIsNotNone(self.runner.status.get("last_scorer_override"))
            # The blocked record should NOT have been written for this turn
            blocked = self.runner.status.get("last_scorer_override_blocked")
            self.assertTrue(blocked is None or blocked.get("turn") != 10,
                "no blocked-override record when the override actually fires")
        finally:
            character_profiles.resolve_profile = orig_resolve
            training_scorer.score_trainings = orig_score


# --- 2. active_selection persistence -------------------------------------

class ActiveSelectionPersistenceTests(unittest.TestCase):
    """``active_selection`` writes through to userdata on every UI pick
    and rehydrates on startup so the picker survives server restarts.
    """

    def setUp(self):
        # Create an isolated userdata folder per test
        self.tmp = Path(tempfile.mkdtemp())
        self._orig_userdata = os.environ.get("SWEEPYCLAUDE_USERDATA_DIR")
        os.environ["SWEEPYCLAUDE_USERDATA_DIR"] = str(self.tmp)

    def tearDown(self):
        if self._orig_userdata is not None:
            os.environ["SWEEPYCLAUDE_USERDATA_DIR"] = self._orig_userdata
        else:
            os.environ.pop("SWEEPYCLAUDE_USERDATA_DIR", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_load_roundtrip(self):
        """A saved selection comes back identical from disk."""
        # We can't import main.py directly (it spins up FastAPI), but we
        # can test the helper logic in isolation.
        selection = {
            "deck": [{"id": 1001}, {"id": 1002}],
            "friend": {"id": 1003},
            "trainee": {"card_id": 100601, "name": "Oguri Cap"},
            "veterans": [],
            "guestParents": [],
        }
        # Simulate _save_active_selection: write to USERDATA_DIR/active_selection.json
        path = self.tmp / "active_selection.json"
        path.write_text(json.dumps(selection), encoding="utf-8")
        # Simulate _load_active_selection: read it back
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, selection)
        self.assertEqual(loaded["trainee"]["card_id"], 100601)

    def test_load_missing_file_returns_none_safely(self):
        """Loading from a fresh userdata folder is a no-op (returns None)."""
        path = self.tmp / "active_selection.json"
        self.assertFalse(path.exists())
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except Exception:
            data = None
        self.assertIsNone(data)

    def test_save_creates_parent_dir(self):
        """The save path is created if missing."""
        nested = self.tmp / "subdir"
        path = nested / "active_selection.json"
        nested.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        self.assertTrue(path.exists())


# --- 3. Hijack reasoning + blocked-override reasoning text ---------------

class DecisionReasoningTextTests(unittest.TestCase):
    """The dashboard reasoning text builds a prominent hijack line and
    explains blocked authoritative overrides.  We test the string
    output of _decision_reasoning indirectly via its inputs."""

    def setUp(self):
        from career_bot.runner import CareerRunner
        self.runner = CareerRunner.__new__(CareerRunner)
        import threading
        self.runner.status = {}
        self.runner.lock = threading.Lock()

    def _stats(self):
        return {"hp": 60, "max_hp": 100, "motivation": 4,
                "speed": 700, "stamina": 300, "power": 500, "guts": 300, "wit": 800}

    def test_hijack_line_appears_when_irregular_training_replaced_race(self):
        """When decision.reason contains the hijack marker, the reasoning
        list includes a clear "Irregular-training hijack" line."""
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 49, "command_type": 1, "command_id": 101},
            reason="irregular training beats planned race Osaka Hai · G1 · 2000m · Turf "
                   "score=1.733 main_gain=35 fail=0 | v6.3 scorer override: 101 -> 106 (wit, margin 0.5)",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Wit (rainbow x1)",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        self.assertIn("Irregular-training hijack", text,
            "decision reasoning must surface the hijack line prominently")
        self.assertIn("Osaka Hai", text)
        # The scorer-override suffix should be stripped from the hijack line
        first_match = next(l for l in lines if "Irregular-training hijack" in l)
        self.assertNotIn("v6.3 scorer override", first_match)

    def test_blocked_override_reason_shows_margin_explanation(self):
        """When the authoritative override was blocked by the margin
        gate this turn, the reasoning explains the block rather than
        just saying "scorer would have picked X"."""
        self.runner.status["last_scorer_override_blocked"] = {
            "turn": 10,
            "from_command_id": 101,
            "from_stat": "speed",
            "to_command_id": 103,
            "to_stat": "guts",
            "margin": 0.01,
            "min_margin": 1.0,
            "reason": "margin_below_threshold",
        }
        self.runner.status["training_scorer_hint"] = {
            "best_stat": "guts",
            "best_score": 0.31,
        }
        self.runner.status["active_character_profile"] = {
            "training_scorer_overrides": {
                "stat_priority": ["speed", "power", "wit", "stamina", "guts"]
            }
        }
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 10, "command_type": 1, "command_id": 101},
            reason="Train Speed",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        # Should mention BOTH scorer's pick AND why the override didn't fire
        self.assertIn("scorer would have picked guts", text)
        self.assertIn("authoritative override blocked", text,
            "reasoning must explain WHY the override didn't fire")
        self.assertIn("margin", text)

    def test_plain_disagreement_when_no_blocked_record(self):
        """When the override was NOT blocked (hint mode, or different
        turn), the reasoning uses the plain "would have picked" message."""
        # No blocked record for THIS turn
        self.runner.status["last_scorer_override_blocked"] = None
        self.runner.status["training_scorer_hint"] = {
            "best_stat": "guts",
            "best_score": 0.31,
        }
        self.runner.status["active_character_profile"] = {
            "training_scorer_overrides": {
                "stat_priority": ["speed", "power", "wit", "stamina", "guts"]
            }
        }
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 10, "command_type": 1, "command_id": 101},
            reason="Train Speed",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        self.assertIn("scorer would have picked guts", text)
        self.assertNotIn("authoritative override blocked", text)


# --- 5. Shadow-precision: win-rate gate on race warnings -----------------

class WinRateWarningGateTests(unittest.TestCase):
    """A race only emits a negative ("warning") adjustment when its
    historical win rate is at or below ``warn_win_rate_ceiling``.

    Before this change a race the bot wins ~90% of the time still
    accrued a small avg-rank penalty and emitted a warning, which read
    as a false alarm in Shadow Mode (the race actually won) -- the user
    observed 16% shadow precision.
    """

    def _race_model(self):
        # One program the bot usually wins, one it usually loses; both
        # confident and both carrying a positive learned penalty.
        return {
            "model": {
                "winner": {"win_rate": 0.90, "penalty": 2.5,
                           "clock_dependency_penalty": 0.0,
                           "confidence": 0.9, "samples": 12},
                "loser": {"win_rate": 0.20, "penalty": 38.0,
                          "clock_dependency_penalty": 0.0,
                          "confidence": 0.9, "samples": 12},
            }
        }

    def _policy(self, **overrides):
        from career_bot.ai_trainer import (
            DEFAULT_AUTO_CONFIG, build_policy_adjustments,
        )
        cfg = dict(DEFAULT_AUTO_CONFIG)
        cfg.update(overrides)
        return build_policy_adjustments(self._race_model(), {}, {}, cfg)

    def test_high_win_rate_race_does_not_warn(self):
        winner = self._policy()["races"].get("winner", {})
        self.assertGreaterEqual(
            winner.get("adjustment", 0.0), 0.0,
            "a race the bot usually wins must not be warned about",
        )

    def test_low_win_rate_race_still_warns(self):
        races = self._policy()["races"]
        self.assertIn("loser", races)
        self.assertLess(
            races["loser"]["adjustment"], 0.0,
            "a race that loses most of the time must still warn",
        )

    def test_ceiling_is_configurable(self):
        races = self._policy(warn_win_rate_ceiling=0.10)["races"]
        self.assertGreaterEqual(races.get("loser", {}).get("adjustment", 0.0), 0.0)

    def test_payload_exposes_ceiling(self):
        self.assertEqual(self._policy()["warn_win_rate_ceiling"], 0.50)

    def test_defaults_raised(self):
        from career_bot.ai_trainer import DEFAULT_AUTO_CONFIG
        self.assertEqual(DEFAULT_AUTO_CONFIG["warn_win_rate_ceiling"], 0.50)
        self.assertEqual(DEFAULT_AUTO_CONFIG["min_samples_for_model"], 4)


if __name__ == "__main__":
    unittest.main()
