"""Regression tests for v7.6.

1. Manual race schedule is never overridden by the race-streak safety
   heuristic. Before v7.6, ``_guide_race_chain_break`` ran for every
   chosen race with no manual-mode bypass (unlike
   ``_irregular_training_decision``, which already guards manual mode).
   Its "unsafe grade" branch fires on OP/PRE-OP races (grade rank < 3),
   and ~70% of DIRT races are OP/PRE-OP (vs ~43% of turf), so the streak
   break dropped user-picked dirt races disproportionately. v7.6 adds a
   manual-mode short-circuit so every hand-picked race runs.
"""
import sys
import unittest
from unittest.mock import MagicMock

# Stub msgpack (sandbox may not have the native dep that the scenario
# package pulls in transitively).
sys.modules.setdefault("msgpack", MagicMock())

from career_bot.scenarios.mant import MantStrategy


class ManualRaceChainBreakGuardTests(unittest.TestCase):
    """``_guide_race_chain_break`` must return None in manual mode even when
    every condition that would normally force a streak-break is met."""

    def _strategy_forced_to_break(self):
        """A MantStrategy instance stubbed so that, absent the manual guard,
        the function WILL substitute a rest/recreation command (return a
        Decision). Lets us prove the guard is what prevents the hijack."""
        s = MantStrategy.__new__(MantStrategy)
        s.trackblazer_guide = {}
        # Long streak so chain_count >= target (forces the break branches).
        s._recent_race_chain_count = lambda data, turn: 99
        # No viable training candidate -> falls through to the HP/grade branch.
        s._best_training_candidate = lambda data, chara, preset: (0.0, None, [])
        s._rest_command = lambda enabled: {"command_id": 1}
        s._recreation_command = lambda enabled: {"command_id": 2}
        s._program_grade_rank = lambda pid: 1  # PRE-OP -> unsafe grade
        s._decision_payload_from_command = lambda cmd, chara: {}
        return s

    def _args(self, source):
        data = {"home_info": {"command_info_array": []}}
        chara = {"turn": 10, "vital": 0}  # vital 0 -> critical HP break
        preset = {"extra_race_list_source": source, "mant_config": {}}
        program_id = 100628
        return data, chara, preset, program_id

    def test_manual_mode_never_chain_breaks(self):
        s = self._strategy_forced_to_break()
        data, chara, preset, pid = self._args("manual")
        self.assertIsNone(
            s._guide_race_chain_break(data, chara, preset, pid),
            "manual race list must never be overridden by the streak heuristic",
        )

    def test_smart_mode_still_chain_breaks(self):
        """Control: with the same break-forcing conditions but NOT manual,
        the function still substitutes a command (proves the test setup
        actually triggers a break, so the manual result is meaningful)."""
        s = self._strategy_forced_to_break()
        data, chara, preset, pid = self._args("smart")
        decision = s._guide_race_chain_break(data, chara, preset, pid)
        self.assertIsNotNone(
            decision,
            "non-manual mode should still apply the race-streak safety break",
        )


if __name__ == "__main__":
    unittest.main()
