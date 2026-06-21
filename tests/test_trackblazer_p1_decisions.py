import tempfile
import unittest
from pathlib import Path

from career_bot.items import MantItemManager, DISPLAY_TO_ID
from career_bot.scenarios.mant import MantStrategy


class FakeClient:
    def __init__(self):
        self.use_payloads = []

    def use_items(self, payload, current_turn):
        self.use_payloads.append((current_turn, list(payload)))
        return {"data": {}}

    def exchange_items(self, payload, current_turn):
        return {"data": {}}


class FakeRacePlanner:
    def __init__(self):
        self.base_dir = Path(tempfile.mkdtemp())
        self.program = {100: {"grade": "G1", "fans": 30000, "name": "Target G1"}}
        self.official_races = {}

    def label(self, program_id):
        return self.program.get(int(program_id), {}).get("name", str(program_id))

    def forced_program(self, state):
        return None

    def choose(self, state, preset):
        return 100


def item_row(name, num=1):
    return {"item_id": DISPLAY_TO_ID[name], "num": num}


def training(command_id=101, gain=90, failure=0):
    main_target = {101: 1, 105: 2, 102: 3, 103: 4, 106: 5}.get(command_id, 1)
    return {
        "command_type": 1,
        "command_id": command_id,
        "command_group_id": 0,
        "select_id": 0,
        "is_enable": 1,
        "failure_rate": failure,
        "training_partner_array": [],
        "params_inc_dec_info_array": [{"target_type": main_target, "value": gain}],
    }


def rest():
    return {"command_type": 7, "command_id": 701, "command_group_id": 701, "is_enable": 1}


def recreation():
    return {"command_type": 3, "command_id": 301, "command_group_id": 301, "is_enable": 1}


def state(turn=30, vital=70, motivation=4, owned=None, commands=None, history=None):
    return {
        "data": {
            "chara_info": {
                "turn": turn,
                "vital": vital,
                "max_vital": 100,
                "motivation": motivation,
                "speed": 300,
                "stamina": 300,
                "power": 300,
                "guts": 300,
                "wiz": 300,
                "skill_point": 0,
            },
            "home_info": {"command_info_array": commands or []},
            "free_data_set": {
                "coin_num": 0,
                "user_item_info_array": [item_row(name, qty) for name, qty in (owned or {}).items()],
                "pick_up_item_info_array": [],
                "item_effect_array": [],
            },
            "action_history": history or [],
        }
    }


class TrackblazerP1DecisionTests(unittest.TestCase):
    def test_irregular_training_hijacks_high_failure_race_when_charm_available(self):
        strategy = MantStrategy(FakeRacePlanner())
        st = state(owned={"Good-Luck Charm": 1}, commands=[training(gain=90, failure=55)])
        decision = strategy.next_decision(st, {"mant_config": {}, "compensate_failure": False})
        self.assertEqual(decision.action, "command")
        self.assertIn("irregular training", decision.reason)
        self.assertEqual(decision.payload["command_id"], 101)
        self.assertNotIn("_irregular_training", decision.payload)

    def test_irregular_training_rejects_high_failure_without_charm(self):
        strategy = MantStrategy(FakeRacePlanner())
        st = state(commands=[training(gain=90, failure=55)])
        decision = strategy.next_decision(st, {"mant_config": {}, "compensate_failure": False})
        self.assertEqual(decision.action, "race")

    def test_race_chain_break_recovers_on_critical_vital(self):
        # This exercises the legacy ("Classic") engine's guide race-chain-break
        # gate, which only runs when the Classic engine is selected. (The default
        # Trackblazer engine has its own energy guard with different reasoning.)
        strategy = MantStrategy(FakeRacePlanner())
        history = [
            {"turn": 27, "action": "race"},
            {"turn": 28, "action": "race"},
            {"turn": 29, "action": "race"},
        ]
        st = state(vital=8, commands=[training(gain=5, failure=0), recreation(), rest()], history=history)
        decision = strategy.next_decision(st, {"mant_config": {"decision_mode": "legacy"}, "compensate_failure": False})
        self.assertEqual(decision.action, "command")
        self.assertEqual(decision.payload["command_type"], 3)
        self.assertIn("race-streak safety", decision.reason)


class TrackblazerP1WhistleTests(unittest.TestCase):
    def test_reset_whistle_only_on_dead_training_turn(self):
        mgr = MantItemManager()
        client = FakeClient()
        dead = training(gain=5, failure=0)
        mgr.use_items(
            client,
            state(vital=70, owned={"Reset Whistle": 1}, commands=[dead]),
            {"mant_config": {}},
            best_command=dead,
            status={"current_chara": {"vital": 70, "motivation": 4}},
        )
        selected = {row["name"] for row in mgr.last_use_selected}
        self.assertIn("Reset Whistle", selected)

        # Same turn: do not spend a second Whistle on the stale pre-shuffle command.
        mgr.use_items(
            client,
            state(vital=70, owned={"Reset Whistle": 1}, commands=[dead]),
            {"mant_config": {}},
            best_command=dead,
            status={"current_chara": {"vital": 70, "motivation": 4}},
        )
        selected = {row["name"] for row in mgr.last_use_selected}
        self.assertNotIn("Reset Whistle", selected)

    def test_reset_whistle_blocked_when_low_energy_is_real_problem(self):
        mgr = MantItemManager()
        client = FakeClient()
        dead = training(gain=5, failure=0)
        mgr.use_items(
            client,
            state(vital=20, owned={"Reset Whistle": 1}, commands=[dead]),
            {"mant_config": {}},
            best_command=dead,
            status={"current_chara": {"vital": 20, "motivation": 4}},
        )
        selected = {row["name"] for row in mgr.last_use_selected}
        self.assertNotIn("Reset Whistle", selected)

    def test_reset_whistle_blocked_during_irregular_training_item_phase(self):
        mgr = MantItemManager()
        client = FakeClient()
        dead = training(gain=5, failure=0)
        dead["_decision_reason"] = "irregular training beats planned race Target G1 score=0.900"
        mgr.use_items(
            client,
            state(vital=70, owned={"Reset Whistle": 1}, commands=[dead]),
            {"mant_config": {}},
            best_command=dead,
            status={"current_chara": {"vital": 70, "motivation": 4}},
        )
        selected = {row["name"] for row in mgr.last_use_selected}
        self.assertNotIn("Reset Whistle", selected)


if __name__ == "__main__":
    unittest.main()
