"""Regression tests for v6.7.10:

  1. Free continue retries are always usable regardless of the Burn
     Clocks toggle.  Paid clocks still require the toggle.
  2. ``_decision_reasoning`` no longer emits the redundant "v6.1 scorer
     agrees" line when an authoritative override fired this turn.  The
     scorer score moves into the override line so info isn't lost.
  3. Items used this turn appear in the reasoning with category-based
     "why" tags.
"""
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("msgpack", MagicMock())


# --- 1. Retry policy free-vs-paid split ----------------------------------

class RetryPolicyFreeVsPaidTests(unittest.TestCase):
    """v6.7.10 contract: free continues are always usable.  Paid clocks
    require ``burn_clocks=True``."""

    def _runner(self, *, burn_clocks):
        from career_bot.runner import CareerRunner
        r = CareerRunner.__new__(CareerRunner)
        r.burn_clocks = burn_clocks
        # _race_grade_for_retry is a method; we stub it out for these
        # unit tests so we don't need a real race_planner.
        r._race_grade_for_retry = lambda program_id: "G1"
        return r

    def _preset(self, **mant_overrides):
        # v1.5: these tests exercise the burn_clocks free/paid fallback, which
        # now applies only when the default-on graded extra-race retry is off.
        base = {"retry_extra_races": False}
        base.update(mant_overrides)
        return {"mant_config": base}

    def test_burn_clocks_off_free_clocks_available_allows_retry(self):
        """v6.7.10 fix: burn_clocks=False but free_clocks>0 -> retry
        is enabled in free-only mode."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            self._preset(), program_id=1234, turn=12, attempts=0,
            free_clocks_available=1,
        )
        self.assertTrue(policy["enabled"], "free clocks must allow retry even when burn_clocks=False")
        self.assertTrue(policy["free_only"])
        self.assertEqual(policy["disabled_reason"], "burn_clocks_disabled_by_user_paid_only")

    def test_burn_clocks_off_no_free_clocks_disables_retry(self):
        """When neither paid (toggle off) nor free (none left) clocks
        are usable, the policy is disabled."""
        runner = self._runner(burn_clocks=False)
        policy = runner._race_retry_policy(
            self._preset(), program_id=1234, turn=12, attempts=0,
            free_clocks_available=0,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "burn_clocks_disabled_by_user")

    def test_burn_clocks_on_allows_paid_and_free(self):
        """With the toggle on, both kinds are usable -- free_only is False."""
        runner = self._runner(burn_clocks=True)
        policy = runner._race_retry_policy(
            self._preset(), program_id=1234, turn=12, attempts=0,
            free_clocks_available=1,
        )
        self.assertTrue(policy["enabled"])
        self.assertFalse(policy["free_only"])

    def test_preset_disable_overrides_everything(self):
        """``disable_race_retries: true`` in the preset must disable
        retries regardless of burn_clocks or free-clocks."""
        runner = self._runner(burn_clocks=True)
        policy = runner._race_retry_policy(
            self._preset(disable_race_retries=True),
            program_id=1234, turn=12, attempts=0, free_clocks_available=1,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "preset_disable_race_retries")

    def test_max_retries_reached_disables(self):
        """When the per-race attempt cap is hit, no further retries
        fire (regardless of toggle / free clock state)."""
        runner = self._runner(burn_clocks=True)
        policy = runner._race_retry_policy(
            self._preset(max_retries_per_race=5),
            program_id=1234, turn=12, attempts=5, free_clocks_available=1,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "max_retries_reached")

    def test_grade_filter_blocks_other_grades(self):
        """When the preset restricts retries to G1 only, a G2/G3 race
        gets rejected even with free clocks and burn_clocks on."""
        runner = self._runner(burn_clocks=True)
        runner._race_grade_for_retry = lambda program_id: "G3"
        policy = runner._race_retry_policy(
            self._preset(retry_race_grades=["G1"]),
            program_id=1234, turn=12, attempts=0, free_clocks_available=1,
        )
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["disabled_reason"], "grade_not_allowed")


# --- 2. "scorer agrees" suppression on override turns --------------------

class ScorerAgreesSuppressionTests(unittest.TestCase):
    """v6.7.10 fix: when an authoritative override fired this turn, the
    "scorer agrees" line is suppressed (it's tautologically true and
    looks contradictory next to "override swapped X -> Y").  The
    scorer score moves into the override line instead."""

    def setUp(self):
        from career_bot.runner import CareerRunner
        self.runner = CareerRunner.__new__(CareerRunner)
        self.runner.status = {}
        self.runner.lock = threading.Lock()

    def _stats(self):
        return {"hp": 100, "max_hp": 100, "motivation": 3,
                "speed": 148, "stamina": 74, "power": 150, "guts": 114, "wit": 201}

    def test_override_fired_suppresses_agrees_line(self):
        """When override fired AND the executed action matches the
        scorer's pick (always the case post-override), the "agrees"
        line must NOT appear -- avoiding the misleading double-message."""
        self.runner.status["last_scorer_override"] = {
            "turn": 1,
            "from_command_id": 102,  # power
            "to_command_id": 106,    # wit
            "to_stat": "wit",
            "margin": 10.19,
        }
        self.runner.status["training_scorer_hint"] = {
            "best_stat": "wit",
            "best_score": 17.66,
        }
        self.runner.status["active_character_profile"] = {
            "training_scorer_overrides": {
                "stat_priority": ["speed", "power", "wit", "stamina", "guts"]
            }
        }
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 1, "command_type": 1, "command_id": 106},
            reason="Train Wit",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Wit",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        # The "scorer agrees" line must NOT appear -- it would be the
        # exact bug the user reported screenshots of.
        self.assertNotIn("scorer agrees", text,
            "v6.7.10: 'scorer agrees' must be suppressed when an override fired this turn")
        # The override line MUST appear and now includes the scorer score.
        self.assertIn("authoritative override swapped", text)
        self.assertIn("power", text)
        self.assertIn("wit", text)
        self.assertIn("scorer score 17.66", text)

    def test_no_override_keeps_agrees_line(self):
        """When the strategy and scorer agreed naturally (no override),
        the "scorer agrees" line stays -- it's informative there."""
        # No override record at all
        self.runner.status["last_scorer_override"] = None
        self.runner.status["training_scorer_hint"] = {
            "best_stat": "speed",
            "best_score": 49.17,
        }
        self.runner.status["active_character_profile"] = {
            "training_scorer_overrides": {
                "stat_priority": ["speed", "power", "wit", "stamina", "guts"]
            }
        }
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 19, "command_type": 1, "command_id": 101},
            reason="Train Speed",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        self.assertIn("scorer agrees", text,
            "'scorer agrees' belongs in the natural-agreement case")
        self.assertIn("49.17", text)

    def test_stale_override_from_different_turn_does_not_suppress(self):
        """An override entry from an OLDER turn must not affect today's
        reasoning (the suppression check is per-turn)."""
        self.runner.status["last_scorer_override"] = {
            "turn": 8,  # different turn
            "from_command_id": 102,
            "to_command_id": 106,
            "to_stat": "wit",
            "margin": 5.0,
        }
        self.runner.status["training_scorer_hint"] = {
            "best_stat": "speed",
            "best_score": 50.0,
        }
        decision = SimpleNamespace(
            action="command",
            payload={"current_turn": 19, "command_type": 1, "command_id": 101},
            reason="Train Speed",
        )
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(), decision=decision, payload=decision.payload,
        )
        text = "\n".join(lines)
        # Stale override is for a different turn -> "agrees" line still appears
        self.assertIn("scorer agrees", text)


# --- 3. Items used reasoning ---------------------------------------------

class ItemsUsedReasoningTests(unittest.TestCase):
    """``_decision_reasoning`` now surfaces a "Items used this turn"
    line with category-based "why" tags."""

    def setUp(self):
        from career_bot.runner import CareerRunner
        self.runner = CareerRunner.__new__(CareerRunner)
        self.runner.status = {}
        self.runner.lock = threading.Lock()
        # Fake item manager carrying selected-this-turn data
        self.runner.item_manager = SimpleNamespace(
            last_use_selected=[],
            last_use_result={},
            use_attempt_events=[],
        )

    def _stats(self):
        return {"hp": 30, "max_hp": 100, "motivation": 2,
                "speed": 100, "stamina": 50, "power": 80, "guts": 60, "wit": 70}

    def _decision(self, turn):
        return SimpleNamespace(
            action="command",
            payload={"current_turn": turn, "command_type": 1, "command_id": 101},
            reason="Train Speed",
        )

    def test_charm_use_is_surfaced_with_protection_reason(self):
        """Charm used -> dashboard reasoning includes the charm protection reason.

        v6.7.10: reasons are now keyed by the canonical item_id (10001 =
        Good-Luck Charm), not display strings."""
        self.runner.item_manager.last_use_selected = [
            {"name": "Good-Luck Charm", "item_id": 10001, "use_num": 1}
        ]
        self.runner.item_manager.last_use_result = {"result": "ok", "turn": 12}
        self.runner.item_manager.use_attempt_events = [{"turn": 12, "selected": [{"name": "Good-Luck Charm"}]}]
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(),
            decision=self._decision(12), payload=self._decision(12).payload,
        )
        text = "\n".join(lines)
        self.assertIn("Items used this turn", text)
        self.assertIn("Good-Luck Charm", text)
        self.assertIn("training-failure protection (charm)", text)

    def test_multiple_items_all_appear_with_their_reasons(self):
        """Multi-item selections list each with its category reason.

        v6.7.10: canonical ids -- 2201 Energy Drink MAX, 2301 Plain Cupcake,
        10001 Good-Luck Charm."""
        self.runner.item_manager.last_use_selected = [
            {"name": "Energy Drink MAX", "item_id": 2201, "use_num": 1},
            {"name": "Plain Cupcake", "item_id": 2301, "use_num": 1},
            {"name": "Good-Luck Charm", "item_id": 10001, "use_num": 1},
        ]
        self.runner.item_manager.last_use_result = {"result": "ok", "turn": 20}
        self.runner.item_manager.use_attempt_events = [{"turn": 20, "selected": []}]
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(),
            decision=self._decision(20), payload=self._decision(20).payload,
        )
        text = "\n".join(lines)
        for item in ("Energy Drink MAX", "Plain Cupcake", "Good-Luck Charm"):
            self.assertIn(item, text)
        # Reasons (canonical id ranges)
        self.assertIn("energy recovery", text)
        self.assertIn("mood boost", text)
        self.assertIn("training-failure protection (charm)", text)

    def test_no_items_used_emits_no_items_line(self):
        """When the manager didn't select anything, no items line is added."""
        self.runner.item_manager.last_use_selected = []
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(),
            decision=self._decision(20), payload=self._decision(20).payload,
        )
        text = "\n".join(lines)
        self.assertNotIn("Items used this turn", text)

    def test_stale_item_selection_from_prior_turn_is_not_attributed(self):
        """If the manager's last selection was for an earlier turn,
        the current turn's reasoning must NOT claim those items were
        used now -- avoid double-counting."""
        self.runner.item_manager.last_use_selected = [
            {"name": "Charm", "item_id": 10001, "use_num": 1}
        ]
        self.runner.item_manager.last_use_result = {"result": "ok", "turn": 5}
        # Last use event was at turn 5; we're now on turn 12.
        self.runner.item_manager.use_attempt_events = [{"turn": 5, "selected": []}]
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(),
            decision=self._decision(12), payload=self._decision(12).payload,
        )
        text = "\n".join(lines)
        self.assertNotIn("Items used this turn", text,
            "stale item state from a prior turn must not be attributed to this turn")

    def test_unknown_item_falls_back_to_category_reason(self):
        """An item not in the explicit id mapping still gets surfaced with an
        id-category reason -- never the old 'selected by item manager'
        artifact.  Adding new items to the bot shouldn't crash this path.

        v6.7.10: id 99999 has no canonical category, so it falls back to the
        generic 'consumable' descriptor."""
        self.runner.item_manager.last_use_selected = [
            {"name": "Mystery Trinket", "item_id": 99999, "use_num": 1}
        ]
        self.runner.item_manager.last_use_result = {"result": "ok", "turn": 30}
        self.runner.item_manager.use_attempt_events = [{"turn": 30, "selected": []}]
        lines = self.runner._decision_reasoning(
            action="train", facility="Train Speed",
            detail="", stats=self._stats(),
            decision=self._decision(30), payload=self._decision(30).payload,
        )
        text = "\n".join(lines)
        self.assertIn("Mystery Trinket", text)
        # The bogus artifact must never appear; a real category reason does.
        self.assertNotIn("selected by item manager", text)
        self.assertIn("consumable", text)


if __name__ == "__main__":
    unittest.main()
