"""v1.5 fan/race-volume work, validated against the Oguri Cap vs Android gap:

  * raising the smart-solver consecutive-race cap (max_races_in_row) from the
    old default of 2 to 5 is the real race-count lever (32 -> 37 scheduled);
  * the curated race agendas resolve cleanly (opt-in epithet bundles);
  * the Trackblazer glow-stick gate now compares EFFECTIVE fans (base x mood/
    scenario multiplier) so it actually fires on real G1s instead of never.
"""
import os
import unittest

from career_bot import trackblazer
from career_bot.items import MantItemManager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RaceAgendaTests(unittest.TestCase):
    def test_agendas_load_and_have_a_recommended_default(self):
        agendas = trackblazer.load_race_agendas(BASE_DIR)
        self.assertTrue(agendas, "race_agendas.json should load at least one agenda")
        ids = {a["id"] for a in agendas}
        self.assertIn("balanced", ids)
        self.assertTrue(any(a.get("recommended") for a in agendas))

    def test_all_agenda_epithets_exist_in_catalog(self):
        raw = trackblazer._load_dataset(BASE_DIR, "epithets") if hasattr(trackblazer, "_load_dataset") else None
        # Resolve the catalog names directly from the structured epithet file.
        import json
        path = os.path.join(BASE_DIR, "data", "trackblazer", "epithets.json")
        data = json.load(open(path, encoding="utf-8"))
        catalog = set(data.keys()) if isinstance(data, dict) else {str(r.get("name") or "").strip() for r in data}
        for agenda in trackblazer.load_race_agendas(BASE_DIR):
            for name in list(agenda.get("target_epithets") or []) + list(agenda.get("forced_epithets") or []):
                self.assertIn(name, catalog, f"agenda {agenda['id']} references unknown epithet {name!r}")

    def test_resolve_and_merge(self):
        t, f = trackblazer.resolve_agenda_epithets(BASE_DIR, "balanced")
        self.assertEqual(len(t), 19)
        self.assertEqual(f, [])
        self.assertEqual(trackblazer.resolve_agenda_epithets(BASE_DIR, ""), ([], []))
        self.assertEqual(trackblazer.resolve_agenda_epithets(BASE_DIR, "nope"), ([], []))
        self.assertEqual(
            trackblazer._merge_epithet_lists(["A", "B"], ["B", "C"], None, [""]),
            ["A", "B", "C"],
        )


class MaxRacesInRowTests(unittest.TestCase):
    def test_raising_cap_schedules_more_races(self):
        apt = {"Sprint": 3, "Mile": 8, "Medium": 7, "Long": 7, "Turf": 7, "Dirt": 7}

        def n(mrir):
            plan = trackblazer.make_schedule(
                BASE_DIR, aptitudes=apt, fan_bonus=0, max_races_in_row=mrir,
                include_op=False, floor=6, solver="auto", target_epithets=[],
                forced_epithets=[], current_turn=1, race_history=[], preset_name="t",
            )
            return int(plan.get("race_count") or 0)

        low, high = n(2), n(5)
        self.assertGreater(high, low, "cap=5 must schedule more races than cap=2")


class GlowStickEffectiveFansTests(unittest.TestCase):
    def setUp(self):
        self.m = MantItemManager.__new__(MantItemManager)
        self.owned = {"Glow Sticks": 2}
        self.cfg = {
            "glow_stick_fan_multiplier": 2.0,
            "trackblazer_glow_stick_min_fans": 20000,
            "trackblazer_glow_stick_final_reserve": 1,
        }

    def test_fires_on_real_senior_g1(self):
        # 13k base -> 26k effective >= 20k threshold (Yasuda Kinen, T59).
        self.assertTrue(self.m._should_use_glow_stick(self.owned, 59, "G1", 13000, self.cfg))
        # 10.5k base -> 21k effective (Victoria Mile, T57).
        self.assertTrue(self.m._should_use_glow_stick(self.owned, 57, "G1", 10500, self.cfg))

    def test_skips_small_g1_and_non_g1(self):
        # 7k base -> 14k effective < 20k (Asahi Hai, T23).
        self.assertFalse(self.m._should_use_glow_stick(self.owned, 23, "G1", 7000, self.cfg))
        # Never on G3.
        self.assertFalse(self.m._should_use_glow_stick(self.owned, 51, "G3", 3900, self.cfg))

    def test_finale_always_uses(self):
        self.assertTrue(self.m._should_use_glow_stick({"Glow Sticks": 1}, 78, "G1", 0, self.cfg))

    def test_old_threshold_would_have_blocked_everything(self):
        # Regression guard: with the multiplier at 1.0 (old base-fans behaviour)
        # a 13k-base G1 does NOT clear 20000 -- proving the old gate never fired.
        old = dict(self.cfg, glow_stick_fan_multiplier=1.0)
        self.assertFalse(self.m._should_use_glow_stick(self.owned, 59, "G1", 13000, old))


if __name__ == "__main__":
    unittest.main()
