"""v1.5: starved-stat pull.

The 2.0x rainbow bonus makes the bot chase whichever stat the rainbows land on,
leaving another stat starved (Wit 656/1000 while Speed gets every rainbow), which
costs the close place-2 race losses.  This whole-score multiplier lifts a
behind-target training so a neglected stat can win the pick -- without touching
target_pressure_strength or the general score scale.
"""
import unittest

from career_bot.scenarios.mant import MantStrategy

TARGETS = [1150, 750, 850, 700, 1000]  # spd, sta, pow, gut, wit


class StarvedStatPullTests(unittest.TestCase):
    def setUp(self):
        self.s = MantStrategy()

    def _mult(self, idx, chara, cfg=None):
        return self.s._starved_stat_multiplier(idx, chara, TARGETS, {"mant_config": cfg or {}})

    def test_starved_stat_gets_boost(self):
        chara = {"speed": 889, "stamina": 540, "power": 672, "guts": 590, "wiz": 760}
        # Wit at 0.76 of target -> boosted above 1.0.
        self.assertGreater(self._mult(4, chara), 1.0)
        # Stamina is most behind (0.72) -> larger boost than wit.
        self.assertGreater(self._mult(1, chara), self._mult(4, chara))

    def test_at_or_above_target_no_boost(self):
        chara = {"speed": 1200, "stamina": 800, "power": 900, "guts": 750, "wiz": 1000}
        for idx in range(5):
            self.assertEqual(self._mult(idx, chara), 1.0)

    def test_deeply_behind_hits_cap(self):
        chara = {"speed": 100, "stamina": 100, "power": 100, "guts": 100, "wiz": 100}
        # Far below target -> clamped at default cap (0.8 -> 1.8x).
        self.assertAlmostEqual(self._mult(4, chara), 1.8, places=3)

    def test_can_be_disabled(self):
        chara = {"speed": 100, "stamina": 100, "power": 100, "guts": 100, "wiz": 100}
        self.assertEqual(self._mult(4, chara, {"enable_starved_stat_pull": False}), 1.0)

    def test_tunable_strength(self):
        chara = {"speed": 889, "stamina": 540, "power": 672, "guts": 590, "wiz": 760}
        weak = self._mult(4, chara, {"starved_stat_strength": 1.0})
        strong = self._mult(4, chara, {"starved_stat_strength": 4.0})
        self.assertLess(weak, strong)

    def test_out_of_range_idx_safe(self):
        chara = {"speed": 100, "wiz": 100}
        self.assertEqual(self._mult(5, chara), 1.0)
        self.assertEqual(self._mult(-1, chara), 1.0)


if __name__ == "__main__":
    unittest.main()
