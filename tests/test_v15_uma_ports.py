"""v1.5: ports from UmaAuto's MANT scenario.

Covers the two genuine feature gaps -- energy-rescue and junior bond-rush --
plus the capped diminishing hint bonus.  (The under-target stat-balance boost
and cap-aware stat curve already existed in Icarus as
``_target_pressure_multiplier`` / ``_cap_adjusted_stat_gain_score`` and are
exercised by the existing trackblazer tests.)
"""
import unittest

from career_bot.scenarios.mant import MantStrategy


def training(command_id=101, gain=40, failure=0, partners=None, tips=None):
    main_target = {101: 1, 105: 2, 102: 3, 103: 4, 106: 5}.get(command_id, 1)
    return {
        "command_type": 1,
        "command_id": command_id,
        "command_group_id": 0,
        "select_id": 0,
        "is_enable": 1,
        "failure_rate": failure,
        "training_partner_array": partners or [],
        "tips_event_partner_array": tips or [],
        "params_inc_dec_info_array": [{"target_type": main_target, "value": gain}],
    }


def rest_cmd():
    return {"command_type": 7, "command_id": 701, "is_enable": 1}


def chara(turn=30, vital=80, bonds=None):
    return {
        "turn": turn,
        "vital": vital,
        "max_vital": 100,
        "motivation": 4,
        "scenario_id": 4,
        "speed": 300, "stamina": 300, "power": 300, "guts": 300, "wiz": 300,
        "skill_point": 0,
        "evaluation_info_array": [
            {"target_id": int(pid), "evaluation": int(value)}
            for pid, value in (bonds or {}).items()
        ],
    }


def data_with(commands, owned=None):
    return {
        "home_info": {"command_info_array": commands},
        "free_data_set": {
            "user_item_info_array": [
                {"item_id": int(iid), "num": int(qty)}
                for iid, qty in (owned or {}).items()
            ]
        },
    }


PRESET = {"compensate_failure": False, "mant_config": {}}


class BondableCountTests(unittest.TestCase):
    def test_counts_only_unbonded_deck_partners(self):
        s = MantStrategy()
        cmd = training(partners=[1, 2, 3])
        # partner 1 already at 80 (bonded), 2 at 40, 3 absent -> 0
        self.assertEqual(s._bondable_count(cmd, chara(bonds={1: 80, 2: 40})), 2)

    def test_empty_command(self):
        self.assertEqual(MantStrategy()._bondable_count(None, chara()), 0)


class JuniorBondRushTests(unittest.TestCase):
    # `bond_train` raises two still-unbonded partners (1, 2); `rainbow` is a
    # higher raw-score turn (two bonded rainbow partners + bigger gain) but
    # bonds nobody new.  Bond-rush should prefer the former in Junior.
    def _data(self):
        bond_train = training(101, gain=30, partners=[1, 2])      # 2 unbonded
        rainbow = training(102, gain=50, partners=[3, 4])         # 0 unbonded, rainbow
        return data_with([bond_train, rainbow])

    def _chara(self, turn):
        return chara(turn=turn, bonds={3: 80, 4: 80})  # 1,2 unbonded; 3,4 rainbow

    def test_junior_prefers_more_unbonded_partners_over_higher_score(self):
        best = MantStrategy()._best_command(self._data(), self._chara(10), PRESET)
        self.assertEqual(best["command_id"], 101)

    def test_outside_junior_highest_score_wins(self):
        best = MantStrategy()._best_command(self._data(), self._chara(30), PRESET)
        self.assertEqual(best["command_id"], 102)

    def test_junior_bond_rush_can_be_disabled(self):
        best = MantStrategy()._best_command(
            self._data(), self._chara(10),
            {"compensate_failure": False, "mant_config": {"junior_bond_rush": False}})
        self.assertEqual(best["command_id"], 102)


class RescueEnergyValueTests(unittest.TestCase):
    def test_picks_smallest_sufficient_item(self):
        s = MantStrategy()
        # vital 40, rest 48, margin 12 -> need to clear 60. Vita 20 -> 60 (not >),
        # Vita 40 -> 80 (sufficient). Owns both; should choose Vita 40 (40), not 65.
        data = data_with([], owned={2001: 3, 2002: 2, 2003: 1})
        self.assertEqual(s._rescue_energy_value(data, vital=40, rest_threshold=48, margin=12), 40)

    def test_none_when_nothing_sufficient(self):
        s = MantStrategy()
        data = data_with([], owned={2001: 5})  # Vita 20 only: 40+20=60, not > 60
        self.assertIsNone(s._rescue_energy_value(data, vital=40, rest_threshold=48, margin=12))

    def test_none_when_no_energy_items(self):
        s = MantStrategy()
        self.assertIsNone(MantStrategy()._rescue_energy_value(data_with([]), 40, 48, 12))


class CanRescueTrainingTests(unittest.TestCase):
    def setUp(self):
        self.s = MantStrategy()
        self.rainbow = training(101, gain=40, failure=0, partners=[1])
        self.ch = chara(vital=40, bonds={1: 80})  # rainbow partner

    def test_rescue_fires_for_rainbow_at_low_vital_with_energy(self):
        data = data_with([], owned={2003: 2})  # Vita 65 above the 1-item reserve
        self.assertTrue(self.s._can_rescue_training(
            data, self.ch, PRESET, self.rainbow, 0.6, vital=40, failure=0, rest_threshold=48))

    def test_no_rescue_without_item_or_charm(self):
        data = data_with([])  # nothing owned
        self.assertFalse(self.s._can_rescue_training(
            data, self.ch, PRESET, self.rainbow, 0.6, vital=40, failure=0, rest_threshold=48))

    def test_no_rescue_for_weak_non_rainbow(self):
        weak = training(101, gain=10, failure=0, partners=[])  # no rainbow, low score
        data = data_with([], owned={2003: 2})
        self.assertFalse(self.s._can_rescue_training(
            data, chara(vital=40), PRESET, weak, 0.10, vital=40, failure=0, rest_threshold=48))

    def test_high_failure_needs_charm(self):
        data_charm = data_with([], owned={10001: 1})
        data_energy = data_with([], owned={2003: 2})
        # failure above hard cap (50) -> only a charm rescues
        self.assertTrue(self.s._can_rescue_training(
            data_charm, self.ch, PRESET, self.rainbow, 0.6, vital=60, failure=55, rest_threshold=48))
        self.assertFalse(self.s._can_rescue_training(
            data_energy, self.ch, PRESET, self.rainbow, 0.6, vital=60, failure=55, rest_threshold=48))

    def test_disabled_via_preset(self):
        data = data_with([], owned={2003: 2})
        off = {"compensate_failure": False, "mant_config": {"rescue_good_training": False}}
        self.assertFalse(self.s._can_rescue_training(
            data, self.ch, off, self.rainbow, 0.6, vital=40, failure=0, rest_threshold=48))


class EnergyRescueInBestCommandTests(unittest.TestCase):
    def test_low_vital_rainbow_runs_training_instead_of_rest(self):
        s = MantStrategy()
        strong = training(101, gain=40, failure=0, partners=[1])
        data = data_with([rest_cmd(), strong], owned={2003: 2})
        best = s._best_command(data, chara(turn=30, vital=40, bonds={1: 80}), PRESET)
        self.assertEqual(best["command_type"], 1)
        self.assertEqual(best["command_id"], 101)
        self.assertTrue(best.get("_energy_rescue"))

    def test_low_vital_no_item_rests(self):
        s = MantStrategy()
        strong = training(101, gain=40, failure=0, partners=[1])
        data = data_with([rest_cmd(), strong], owned={})  # nothing to rescue with
        best = s._best_command(data, chara(turn=30, vital=40, bonds={1: 80}), PRESET)
        self.assertEqual(best["command_type"], 7)


class HintScalingTests(unittest.TestCase):
    def cfg(self):
        return {"compensate_failure": False,
                "mant_config": {"enable_prioritize_skill_hints": True}}

    def test_more_hints_score_higher(self):
        s = MantStrategy()
        data = {"home_info": {"command_info_array": []}}
        one = training(101, partners=[1, 2, 3, 4, 5], tips=[1])
        four = training(101, partners=[1, 2, 3, 4, 5], tips=[1, 2, 3, 4])
        self.assertGreater(
            s._score_command(four, data, chara(), self.cfg()),
            s._score_command(one, data, chara(), self.cfg()),
        )

    def test_hint_count_capped_at_four(self):
        s = MantStrategy()
        data = {"home_info": {"command_info_array": []}}
        four = training(101, partners=[1, 2, 3, 4, 5], tips=[1, 2, 3, 4])
        five = training(101, partners=[1, 2, 3, 4, 5], tips=[1, 2, 3, 4, 5])
        self.assertAlmostEqual(
            s._score_command(four, data, chara(), self.cfg()),
            s._score_command(five, data, chara(), self.cfg()),
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
