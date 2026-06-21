"""Regression tests for v7.6.3 support-card effect type mapping.

The Deck Bonuses bug was a subtle off-by-one in `_SUPPORT_EFFECT_LABELS`
(career_bot/master_data.py): from type id 8 onward every effect was mislabeled,
so "race bonus" read the wrong field and a deck showed impossible totals like
+105%. A master-data re-sync could silently reintroduce a shift, so these tests:

  1. LOCK the canonical type->label mapping for the critical ids.
  2. Assert the live resolved data has realistic per-effect caps — this fails
     loudly if the data is ever regenerated with a shifted/wrong mapping.

Authoritative source: Umamusume Wiki Module:Game/Supports/Data/Effects,
cross-verified against gametora.com card pages.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from career_bot.master_data import _SUPPORT_EFFECT_LABELS

DATA = Path(__file__).resolve().parents[1] / "data" / "support_effects_resolved_core.json"


class EffectTypeMapLockTests(unittest.TestCase):
    """If any of these change, deck-bonus values silently break — fail hard."""

    EXPECTED = {
        1: "friendship_bonus",
        2: "mood_effect",
        3: "speed_bonus",
        7: "wit_bonus",
        8: "training_effectiveness",   # NOT initial_speed (the old bug)
        9: "initial_speed",
        14: "initial_friendship_gauge",
        15: "race_bonus",              # NOT fan_bonus (the old bug)
        16: "fan_bonus",
        17: "hint_levels",
        18: "hint_frequency",
        19: "specialty_priority",
        30: "skill_point_bonus",
        31: "wit_friendship_recovery",
        32: "initial_skill_points",
    }

    def test_canonical_mapping_locked(self):
        for type_id, label in self.EXPECTED.items():
            self.assertEqual(
                _SUPPORT_EFFECT_LABELS.get(type_id), label,
                f"type {type_id} must map to '{label}' (got '{_SUPPORT_EFFECT_LABELS.get(type_id)}'). "
                "A mismatch means the effect mapping shifted again — deck bonuses will be wrong.",
            )


class ResolvedDataSanityTests(unittest.TestCase):
    """The live data must have realistic effect magnitudes. Catches a re-sync
    that regenerated with a bad mapping (e.g. race_bonus jumping to 35)."""

    # (effect key, inclusive max allowed across all cards/levels)
    CAPS = {
        "race_bonus": 12,        # real cap ~10%
        "fan_bonus": 40,
        "friendship_bonus": 45,
        "training_effectiveness": 25,
        "mood_effect": 70,
        "hint_levels": 5,        # a level count, not a percent
    }

    @classmethod
    def setUpClass(cls):
        if not DATA.exists():
            raise unittest.SkipTest(f"{DATA} not present")
        blob = json.loads(DATA.read_text(encoding="utf-8"))
        cls.cards = blob.get("support_cards") if isinstance(blob, dict) else blob

    def _max_of(self, key):
        mx = 0
        for c in self.cards:
            for row in (c.get("effect_values_by_level") or {}).values():
                v = row.get(key)
                if isinstance(v, (int, float)) and v > mx:
                    mx = v
        return mx

    def test_effect_caps_are_realistic(self):
        for key, cap in self.CAPS.items():
            mx = self._max_of(key)
            self.assertLessEqual(
                mx, cap,
                f"{key} max across all cards is {mx}, exceeding the realistic cap {cap}. "
                "The effect mapping is probably shifted again — re-check _SUPPORT_EFFECT_LABELS.",
            )

    def test_race_bonus_is_present_and_small(self):
        """Race bonus should exist (some cards have it) but be small (~<=10)."""
        mx = self._max_of("race_bonus")
        self.assertGreater(mx, 0, "no race_bonus values at all — mapping may be wrong")
        self.assertLessEqual(mx, 12)


if __name__ == "__main__":
    unittest.main()
