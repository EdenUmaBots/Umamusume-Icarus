"""v6.8: parent/deck-aware stamina target adaptation + profile plumbing."""
import unittest

from career_bot import training_scorer as ts
from career_bot.character_profiles import CharacterProfile


def _chara(stamina, turn, mile=7):
    return {
        "stamina": stamina, "turn": turn,
        "proper_distance_short": 5, "proper_distance_mile": mile,
        "proper_distance_middle": 5, "proper_distance_long": 5,
    }


class AdaptStaminaTargetsTests(unittest.TestCase):
    def _cfg(self):
        return ts.TrainingScorerConfig()  # mile stamina target = 600 by default

    def test_disabled_returns_same_config(self):
        cfg = self._cfg()
        out = ts.adapt_stamina_targets(cfg, _chara(100, 60), enabled=False, turn=60)
        self.assertIs(out, cfg)

    def test_early_turn_unchanged(self):
        cfg = self._cfg()
        out = ts.adapt_stamina_targets(cfg, _chara(50, 20), enabled=True, turn=20)
        self.assertIs(out, cfg)

    def test_on_pace_unchanged(self):
        cfg = self._cfg()
        # stamina 500 at turn 60 -> projected ~650 >= 0.8*600; leave alone.
        out = ts.adapt_stamina_targets(cfg, _chara(500, 60), enabled=True, turn=60)
        self.assertEqual(out.stat_targets["mile"]["stamina"], 600)

    def test_lagging_relaxes_target(self):
        cfg = self._cfg()
        # stamina 100 at turn 60 -> projected ~130 << 0.8*600; relax to floor 400.
        out = ts.adapt_stamina_targets(cfg, _chara(100, 60), enabled=True, turn=60)
        self.assertEqual(out.stat_targets["mile"]["stamina"], 400)
        # purity: original config untouched.
        self.assertEqual(cfg.stat_targets["mile"]["stamina"], 600)

    def test_relax_never_raises_above_original(self):
        cfg = self._cfg()
        out = ts.adapt_stamina_targets(cfg, _chara(100, 60), enabled=True, turn=60)
        self.assertLessEqual(out.stat_targets["mile"]["stamina"],
                             cfg.stat_targets["mile"]["stamina"])

    def test_target_at_floor_unchanged(self):
        cfg = self._cfg()
        cfg.stat_targets["mile"]["stamina"] = 400  # already at floor
        out = ts.adapt_stamina_targets(cfg, _chara(50, 60), enabled=True, turn=60)
        self.assertIs(out, cfg)


class ProfilePlumbingTests(unittest.TestCase):
    def test_to_dict_includes_flag(self):
        p = CharacterProfile(
            profile_id="x", display_name="X", matched_via="card_id", scenario_id=4,
            adapt_targets_to_inheritance=True)
        self.assertTrue(p.to_dict()["adapt_targets_to_inheritance"])

    def test_default_flag_false(self):
        p = CharacterProfile(
            profile_id="x", display_name="X", matched_via="default", scenario_id=4)
        self.assertFalse(p.to_dict()["adapt_targets_to_inheritance"])


if __name__ == "__main__":
    unittest.main()
