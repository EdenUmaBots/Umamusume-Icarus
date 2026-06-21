"""Tests for the v6.2 character-profile system.

Covers:
  - ``resolve_profile`` lookup paths: by card_id, by chara_id, by preset,
    default fallback when nothing matches, default fallback when the matched
    file is missing
  - Per-scenario overrides: scenario block stomps base values, lists are
    replaced (not appended), dict fields shallow-merge
  - ``training_scorer_config`` builds a real ``TrainingScorerConfig`` from
    the override dict and silently ignores unknown keys
  - ``solver_weight_overrides`` returns a flat dict suitable for the solver
  - ``epithet_goals`` returns ``(target, forced)`` lists
  - Mode normalization (hint / authoritative / disabled / unknown -> hint)
  - End-to-end resolution against the shipped Oguri Cap profile
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

from career_bot import character_profiles
from career_bot import training_scorer as ts


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------


def write_profile_set(base_dir: Path, index: Dict[str, Any], profiles: Dict[str, Dict[str, Any]]) -> None:
    """Materialize a profiles directory under ``base_dir/data/character_profiles/``."""
    pdir = base_dir / "data" / character_profiles.PROFILES_DIRNAME
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / character_profiles.INDEX_FILENAME).write_text(json.dumps(index), encoding="utf-8")
    for name, payload in profiles.items():
        (pdir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------
# Resolution lookup tests
# --------------------------------------------------------------------------


class ResolveProfileTests(unittest.TestCase):
    def test_default_fallback_when_no_index(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # No profiles dir, no index, no files.
            profile = character_profiles.resolve_profile(card_id=12345, base_dir=base)
            self.assertEqual(profile.profile_id, "default")
            self.assertEqual(profile.matched_via, "default")
            self.assertEqual(profile.training_scorer_overrides, {})
            self.assertEqual(profile.solver_overrides, {})

    def test_default_fallback_when_matched_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Index points to a profile that doesn't exist on disk.
            write_profile_set(base, {"by_card_id": {"42": "nonexistent"}}, {})
            profile = character_profiles.resolve_profile(card_id=42, base_dir=base)
            self.assertEqual(profile.profile_id, "default")
            self.assertEqual(profile.matched_via, "default")

    def test_resolves_by_card_id(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"100601": "oguri_cap"}, "by_chara_id": {}, "by_preset": {}},
                {"oguri_cap": {"display_name": "Oguri Cap"}, "default": {"display_name": "Default"}},
            )
            profile = character_profiles.resolve_profile(card_id=100601, base_dir=base)
            self.assertEqual(profile.profile_id, "oguri_cap")
            self.assertEqual(profile.matched_via, "card_id")
            self.assertEqual(profile.display_name, "Oguri Cap")

    def test_resolves_by_chara_id_when_card_id_misses(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {}, "by_chara_id": {"1006": "oguri_cap"}, "by_preset": {}},
                {"oguri_cap": {"display_name": "Oguri Cap"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=99999, chara_id=1006, base_dir=base)
            self.assertEqual(profile.profile_id, "oguri_cap")
            self.assertEqual(profile.matched_via, "chara_id")

    def test_resolves_by_preset_name_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {}, "by_chara_id": {}, "by_preset": {"oguri farming": "oguri_cap"}},
                {"oguri_cap": {"display_name": "Oguri Cap"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=0, chara_id=0, preset_name="Oguri Farming", base_dir=base)
            self.assertEqual(profile.profile_id, "oguri_cap")
            self.assertEqual(profile.matched_via, "preset")

    def test_card_id_beats_chara_id_when_both_match(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {
                    "by_card_id": {"100601": "oguri_card_variant"},
                    "by_chara_id": {"1006": "oguri_cap"},
                    "by_preset": {},
                },
                {"oguri_cap": {}, "oguri_card_variant": {}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=100601, chara_id=1006, base_dir=base)
            self.assertEqual(profile.profile_id, "oguri_card_variant")
            self.assertEqual(profile.matched_via, "card_id")


# --------------------------------------------------------------------------
# Per-scenario override tests
# --------------------------------------------------------------------------


class ScenarioOverrideTests(unittest.TestCase):
    def test_scenario_block_overrides_base_dict_fields_shallow(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "display_name": "X",
                        "solver_overrides": {"longDistanceStaminaFloor": 550, "epithetValue": 1.0},
                        "scenarios": {
                            "4": {"solver_overrides": {"longDistanceStaminaFloor": 450}}
                        },
                    },
                    "default": {},
                },
            )
            scen4 = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            scen1 = character_profiles.resolve_profile(card_id=1, scenario_id=1, base_dir=base)
            # Scenario 4 overrides the floor but base epithetValue still survives.
            self.assertEqual(scen4.solver_overrides.get("longDistanceStaminaFloor"), 450)
            self.assertEqual(scen4.solver_overrides.get("epithetValue"), 1.0)
            # Scenario 1 has no override; base values flow through.
            self.assertEqual(scen1.solver_overrides.get("longDistanceStaminaFloor"), 550)

    def test_scenario_block_replaces_list_fields_entirely(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "target_epithets": ["Base Epithet"],
                        "scenarios": {"4": {"target_epithets": ["Scenario Epithet"]}},
                    },
                    "default": {},
                },
            )
            scen4 = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            # Replacement, not concat
            self.assertEqual(scen4.target_epithets, ["Scenario Epithet"])

    def test_scenario_without_override_inherits_base_lists(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {"target_epithets": ["Base"], "scenarios": {"4": {}}},
                    "default": {},
                },
            )
            scen4 = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            self.assertEqual(scen4.target_epithets, ["Base"])


# --------------------------------------------------------------------------
# Conversion accessors
# --------------------------------------------------------------------------


class TrainingScorerConfigTests(unittest.TestCase):
    def test_overrides_apply_to_config(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "training_scorer_overrides": {
                            "stat_priority": ["wit", "speed", "stamina", "power", "guts"],
                            "rainbow_bonus_enabled": True,
                            "max_failure_chance": 35,
                        },
                    },
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            cfg = profile.training_scorer_config()
            self.assertEqual(cfg.stat_priority[0], "wit")
            self.assertTrue(cfg.rainbow_bonus_enabled)
            self.assertEqual(cfg.max_failure_chance, 35)
            # Untouched fields keep their defaults
            self.assertEqual(cfg.weight_stat_efficiency, 0.60)

    def test_unknown_override_keys_are_silently_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {"training_scorer_overrides": {"this_field_does_not_exist": 12345}},
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            cfg = profile.training_scorer_config()  # Must not raise
            self.assertFalse(hasattr(cfg, "this_field_does_not_exist"))

    def test_stat_targets_override_propagates_to_config(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            tuned = {
                "long": {"speed": 1050, "stamina": 1100, "power": 1000, "guts": 400, "wit": 1000},
            }
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {"training_scorer_overrides": {"stat_targets": tuned}},
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            cfg = profile.training_scorer_config()
            self.assertEqual(cfg.stat_targets["long"]["stamina"], 1100)


class SolverWeightOverridesTests(unittest.TestCase):
    def test_returns_flat_dict_for_solver(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "solver_overrides": {"epithetValue": 2.0, "targetOptionalRaceCount": 40},
                        "scenarios": {
                            "4": {"solver_overrides": {"longDistanceStaminaFloor": 450}}
                        },
                    },
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            weights = profile.solver_weight_overrides()
            self.assertEqual(weights["epithetValue"], 2.0)
            self.assertEqual(weights["targetOptionalRaceCount"], 40)
            self.assertEqual(weights["longDistanceStaminaFloor"], 450)


class EpithetGoalsTests(unittest.TestCase):
    def test_returns_target_and_forced(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "target_epithets": ["Arima Kinen Winner"],
                        "forced_epithets": ["Has-Beens-League Champion"],
                    },
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            target, forced = profile.epithet_goals()
            self.assertEqual(target, ["Arima Kinen Winner"])
            self.assertEqual(forced, ["Has-Beens-League Champion"])

    def test_empty_lists_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            profile = character_profiles.resolve_profile(card_id=0, base_dir=base)
            self.assertEqual(profile.epithet_goals(), ([], []))


# --------------------------------------------------------------------------
# Mode normalization
# --------------------------------------------------------------------------


class TrainingScorerModeTests(unittest.TestCase):
    def test_default_mode_is_hint(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            profile = character_profiles.resolve_profile(card_id=0, base_dir=base)
            self.assertEqual(profile.training_scorer_mode, "hint")

    def test_authoritative_mode_loads(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {"x": {"training_scorer_mode": "authoritative"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            self.assertEqual(profile.training_scorer_mode, "authoritative")

    def test_unknown_mode_falls_back_to_hint(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {"x": {"training_scorer_mode": "yolo"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            self.assertEqual(profile.training_scorer_mode, "hint")

    def test_disabled_mode_loads(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {"x": {"training_scorer_mode": "disabled"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            self.assertEqual(profile.training_scorer_mode, "disabled")

    def test_per_scenario_mode_override(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "training_scorer_mode": "hint",
                        "scenarios": {"4": {"training_scorer_mode": "authoritative"}},
                    },
                    "default": {},
                },
            )
            scen1 = character_profiles.resolve_profile(card_id=1, scenario_id=1, base_dir=base)
            scen4 = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            self.assertEqual(scen1.training_scorer_mode, "hint")
            self.assertEqual(scen4.training_scorer_mode, "authoritative")


# --------------------------------------------------------------------------
# Shipped-profile regression
# --------------------------------------------------------------------------


class ShippedProfilesRegressionTests(unittest.TestCase):
    """Smoke-tests the actual profiles shipped under data/character_profiles/."""

    def test_oguri_cap_resolves_by_card_id(self):
        # base_dir here is the v6 repo root which contains data/character_profiles/
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "oguri_cap")
        self.assertEqual(profile.matched_via, "card_id")
        self.assertEqual(profile.display_name, "Oguri Cap")

    def test_oguri_cap_resolves_by_chara_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=0, chara_id=1006, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "oguri_cap")
        self.assertEqual(profile.matched_via, "chara_id")

    def test_oguri_cap_trackblazer_overrides_apply(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base_dir)
        # Scenario-4 solver overrides flow through (v6.6 tuning: real
        # levers replace the no-op targetOptionalRaceCount)
        weights = profile.solver_weight_overrides()
        self.assertEqual(weights["longDistanceStaminaFloor"], 450)
        self.assertEqual(weights["epithetValue"], 3.0)
        self.assertEqual(weights["raceCostPct"], 75.0)
        self.assertEqual(weights["lateSeniorRacePressure"], 20.0)
        # Base training_scorer overrides reach the config
        cfg = profile.training_scorer_config()
        self.assertEqual(cfg.stat_priority, ["speed", "power", "stamina", "wit", "guts"])
        self.assertTrue(cfg.rainbow_bonus_enabled)
        self.assertEqual(cfg.stat_targets["long"]["stamina"], 1100)
        # Preferred distances reach through
        self.assertIn("mile", profile.preferred_distances)
        self.assertIn("medium", profile.preferred_distances)

    def test_unknown_trainee_falls_back_to_default(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=999999, chara_id=999999, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "default")
        self.assertEqual(profile.training_scorer_overrides, {})
        self.assertEqual(profile.solver_overrides, {})
        self.assertEqual(profile.training_scorer_mode, "hint")

    def test_oguri_cap_produces_usable_training_scorer(self):
        """End-to-end: load Oguri profile, get a TrainingScorerConfig, run
        the scorer on a realistic command payload, verify it doesn't crash
        and produces sensible output."""
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base_dir)
        cfg = profile.training_scorer_config()
        chara = {
            "speed": 600, "stamina": 250, "power": 500, "guts": 200, "wiz": 400,
            "evaluation_info_array": [{"support_card_id": 4, "evaluation": 85}],
            "proper_distance_mile": 8,  # S
            "proper_distance_middle": 7,
            "proper_distance_short": 5,
            "proper_distance_long": 6,
        }
        home_info = {
            "command_info_array": [
                {"command_type": 1, "command_id": 101, "is_enable": 1,
                 "training_partner_array": [4], "tips_event_partner_array": [],
                 "params_inc_dec_info_array": [{"target_type": 1, "value": 12}],
                 "failure_rate": 0, "level": 3},
            ]
        }
        scores = ts.score_trainings(home_info, chara, config=cfg)
        self.assertEqual(len(scores), 1)
        self.assertGreater(scores[0].score, 0)
        self.assertIsNone(scores[0].skipped_reason)


# --------------------------------------------------------------------------
# Listing helper
# --------------------------------------------------------------------------


class ListAvailableProfilesTests(unittest.TestCase):
    def test_lists_shipped_profiles(self):
        base_dir = Path(__file__).resolve().parent.parent
        listed = character_profiles.list_available_profiles(base_dir)
        ids = {p["profile_id"] for p in listed}
        self.assertIn("default", ids)
        self.assertIn("oguri_cap", ids)
        # Oguri Cap has scenario 4 overrides
        oguri_row = next(p for p in listed if p["profile_id"] == "oguri_cap")
        self.assertIn("4", oguri_row["scenarios_with_overrides"])

    def test_empty_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(character_profiles.list_available_profiles(Path(td)), [])


# --------------------------------------------------------------------------
# v6.3 -- auto-derivation from live chara aptitudes
# --------------------------------------------------------------------------


def make_chara(*, name="", sprint=0, mile=0, medium=0, long_=0, **extra):
    """Helper to build a chara_info-shaped dict with aptitude fields."""
    out = {
        "proper_distance_short": sprint,
        "proper_distance_mile": mile,
        "proper_distance_middle": medium,
        "proper_distance_long": long_,
    }
    if name:
        out["trained_chara_name"] = name
    out.update(extra)
    return out


class AutoDerivationTests(unittest.TestCase):
    """The chara_info-aware path of resolve_profile."""

    def test_long_stayer_gets_stamina_priority(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = make_chara(name="Test Stayer", long_=8, medium=7, mile=5, sprint=2)
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertEqual(profile.matched_via, "auto")
            self.assertEqual(profile.derivation, "auto_derived")
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][0], "stamina")

    def test_miler_gets_speed_priority(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = make_chara(name="Test Miler", mile=8, medium=7, sprint=5, long_=4)
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertEqual(profile.matched_via, "auto")
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][0], "speed")
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][1], "power")

    def test_sprinter_gets_speed_power_priority(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = make_chara(name="Test Sprinter", sprint=8, mile=6, medium=3, long_=1)
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][0], "speed")
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][1], "power")

    def test_stamina_floor_scales_with_long_aptitude(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Strong stayer -> default 550 floor
            strong = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base,
                chara_info=make_chara(long_=8, medium=7, mile=5, sprint=2),
            )
            # Weak stayer (no Long aptitude) -> low floor (don't penalize)
            weak = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base,
                chara_info=make_chara(sprint=8, mile=6, medium=3, long_=1),
            )
            self.assertEqual(strong.solver_overrides["longDistanceStaminaFloor"], 550)
            self.assertLess(weak.solver_overrides["longDistanceStaminaFloor"], 550)

    def test_preferred_distances_include_b_grade_and_above(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = make_chara(mile=8, medium=7, long_=6, sprint=3)
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertIn("mile", profile.preferred_distances)
            self.assertIn("medium", profile.preferred_distances)
            self.assertIn("long", profile.preferred_distances)
            self.assertNotIn("sprint", profile.preferred_distances)

    def test_per_distance_targets_scale_with_aptitude(self):
        """A weak-distance target should be lower than a strong-distance one."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = make_chara(long_=8, medium=7, mile=5, sprint=2)
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            targets = profile.training_scorer_overrides["stat_targets"]
            # Sprint (rank 2 = E) is much weaker than Long (rank 8 = S)
            self.assertLess(targets["sprint"]["speed"], targets["long"]["speed"])

    def test_rainbow_bonus_enabled_for_s_aptitude(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # S-grade Mile aptitude (rank 8)
            chara_s = make_chara(mile=8, medium=7, sprint=5, long_=4)
            # A-grade Mile aptitude (rank 7) -- still strong but not S
            chara_a = make_chara(mile=7, medium=7, sprint=5, long_=4)
            s_prof = character_profiles.resolve_profile(card_id=99999, scenario_id=4, base_dir=base, chara_info=chara_s)
            a_prof = character_profiles.resolve_profile(card_id=99999, scenario_id=4, base_dir=base, chara_info=chara_a)
            self.assertTrue(s_prof.training_scorer_overrides.get("rainbow_bonus_enabled"))
            self.assertNotIn("rainbow_bonus_enabled", a_prof.training_scorer_overrides)

    def test_letter_grade_aptitudes_also_work(self):
        """Aptitudes can come in as letter grades ('A', 'B', ...) or as
        numeric ranks; both should be handled."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            chara = {
                "trained_chara_name": "Test Letter Grade",
                "proper_distance_short": "F",
                "proper_distance_mile": "S",
                "proper_distance_middle": "A",
                "proper_distance_long": "C",
            }
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertEqual(profile.matched_via, "auto")
            self.assertEqual(profile.training_scorer_overrides["stat_priority"][0], "speed")  # Mile=S

    def test_falls_back_to_default_when_no_aptitudes(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # chara_info present but no aptitudes -> auto can't derive
            chara = {"chara_name": "Mystery"}
            profile = character_profiles.resolve_profile(
                card_id=99999, scenario_id=4, base_dir=base, chara_info=chara
            )
            self.assertEqual(profile.matched_via, "default")

    def test_hand_curated_still_wins_over_auto(self):
        """Even when chara_info is provided, a hand-curated profile match
        should take precedence."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1006": "oguri_cap"}, "by_chara_id": {}, "by_preset": {}},
                {
                    "oguri_cap": {"display_name": "Oguri Cap (curated)"},
                    "default": {},
                },
            )
            chara = make_chara(name="Whoever", mile=8, medium=7)
            profile = character_profiles.resolve_profile(
                card_id=1006, scenario_id=4, base_dir=base, chara_info=chara,
            )
            self.assertEqual(profile.matched_via, "card_id")
            self.assertEqual(profile.derivation, "hand_curated")
            self.assertEqual(profile.display_name, "Oguri Cap (curated)")

    def test_legacy_no_chara_info_still_works(self):
        """Callers that don't pass chara_info (pre-v6.3 callsites) still
        get a usable profile via the default path."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            profile = character_profiles.resolve_profile(card_id=99999, scenario_id=4, base_dir=base)
            self.assertEqual(profile.matched_via, "default")


class SuggestedEpithetsTests(unittest.TestCase):
    """Auto-derivation should populate ``suggested_epithets`` when the
    trainee's name matches an entry in the bundled epithet catalog."""

    def test_known_character_gets_suggested_epithets(self):
        base = Path(__file__).resolve().parent.parent  # repo root
        chara = make_chara(name="Oguri Cap", mile=8, medium=7, sprint=5, long_=4)
        profile = character_profiles.resolve_profile(
            card_id=99999, chara_id=99999, scenario_id=4,
            base_dir=base, chara_info=chara,
        )
        # Even though we passed unknown IDs (so resolution went via auto-
        # derivation), the catalog lookup by name should yield Oguri's
        # signature epithet.
        self.assertGreater(len(profile.suggested_epithets), 0)
        self.assertIn("Oguri Cap", profile.suggested_epithets[0].get("characters") or [])

    def test_hand_curated_oguri_also_gets_suggested_epithets(self):
        """The hand-curated path should also surface suggested_epithets
        via display_name lookup."""
        base = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base)
        self.assertEqual(profile.profile_id, "oguri_cap")
        self.assertGreater(len(profile.suggested_epithets), 0)


# --------------------------------------------------------------------------
# Shipped Special Week profile (added in v6.3)
# --------------------------------------------------------------------------


class SpecialWeekProfileTests(unittest.TestCase):
    def test_special_week_resolves_by_card_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100101, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "special_week")
        self.assertEqual(profile.matched_via, "card_id")

    def test_special_week_has_stamina_priority(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100101, scenario_id=4, base_dir=base_dir)
        cfg = profile.training_scorer_config()
        self.assertEqual(cfg.stat_priority[0], "stamina")
        # Long should have very high stamina target
        self.assertEqual(cfg.stat_targets["long"]["stamina"], 1200)


# --------------------------------------------------------------------------
# v6.5 -- the three new hand-curated profiles
# --------------------------------------------------------------------------


class SakuraBakushinOProfileTests(unittest.TestCase):
    def test_resolves_by_card_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=104101, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "sakura_bakushin_o")
        self.assertEqual(profile.matched_via, "card_id")

    def test_resolves_by_chara_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=0, chara_id=1041, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "sakura_bakushin_o")

    def test_sprinter_tuning(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=104101, scenario_id=4, base_dir=base_dir)
        cfg = profile.training_scorer_config()
        # Pure sprinter -> Speed/Power top, low Stamina target
        self.assertEqual(cfg.stat_priority[0], "speed")
        self.assertEqual(cfg.stat_priority[1], "power")
        # Sprint target should be full strength
        self.assertEqual(cfg.stat_targets["sprint"]["speed"], 1200)
        # Long-distance stamina floor lowered for a sprinter
        self.assertEqual(profile.solver_overrides["longDistanceStaminaFloor"], 300)
        # Preferred distances are sprint + mile only
        self.assertEqual(set(profile.preferred_distances), {"sprint", "mile"})


class DaiwaScarletProfileTests(unittest.TestCase):
    def test_resolves_by_card_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100901, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "daiwa_scarlet")

    def test_mile_med_tuning(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100901, scenario_id=4, base_dir=base_dir)
        cfg = profile.training_scorer_config()
        self.assertEqual(cfg.stat_priority[0], "speed")
        # Mile/Medium specialist
        self.assertEqual(set(profile.preferred_distances), {"mile", "medium"})
        # Long-distance stamina floor between Sakura's 300 and Oguri's 450
        self.assertEqual(profile.solver_overrides["longDistanceStaminaFloor"], 425)


class TokaiTeioProfileTests(unittest.TestCase):
    def test_resolves_by_card_id(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100301, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "tokai_teio")

    def test_tokai_alt_card_also_resolves(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100302, scenario_id=4, base_dir=base_dir)
        self.assertEqual(profile.profile_id, "tokai_teio")

    def test_medium_long_tuning(self):
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100301, scenario_id=4, base_dir=base_dir)
        cfg = profile.training_scorer_config()
        self.assertEqual(cfg.stat_priority[0], "stamina")
        self.assertEqual(set(profile.preferred_distances), {"medium", "long"})


class AllShippedProfilesAutoPickSignaturesTests(unittest.TestCase):
    """Each of the 5 hand-curated profiles should auto-pick its signature
    epithet from the catalog (when target_epithets is empty in JSON)."""

    def test_each_profile_gets_signature(self):
        """v6.7.6: auto_pick_epithets defaults to False, so shipped
        profiles no longer auto-pick a signature unless the user opts
        in.  This test now verifies that signature lookup *works* (the
        catalog still maps each character -> their signature epithet)
        but checks auto_picked_epithets only when auto_pick is on.
        """
        base_dir = Path(__file__).resolve().parent.parent
        expected = [
            (104101, "sakura_bakushin_o"),
            (100901, "daiwa_scarlet"),
            (100301, "tokai_teio"),
            (100601, "oguri_cap"),
            (100101, "special_week"),
        ]
        for card_id, expected_id in expected:
            with self.subTest(card_id=card_id):
                # Profile resolves correctly (the identity layer still works)
                profile = character_profiles.resolve_profile(
                    card_id=card_id, scenario_id=4, base_dir=base_dir,
                )
                self.assertEqual(profile.profile_id, expected_id)
                # v6.7.6: by default, auto-pick is OFF so the array is empty.
                self.assertEqual(
                    profile.auto_picked_epithets, [],
                    f"v6.7.6 default: {expected_id} auto-pick is OFF",
                )
                # But if the user opts in, the catalog still produces a
                # non-empty signature.  Force the flag and re-resolve to
                # verify signature lookup is intact.
                forced_payload_path = base_dir / "data" / "character_profiles" / f"{expected_id}.json"
                if forced_payload_path.exists():
                    raw = json.loads(forced_payload_path.read_text(encoding="utf-8"))
                    raw["auto_pick_epithets"] = True
                    # Resolve via a temp dir override
                    with tempfile.TemporaryDirectory() as td:
                        td_path = Path(td)
                        tgt_dir = td_path / "data" / "character_profiles"
                        tgt_dir.mkdir(parents=True)
                        (tgt_dir / f"{expected_id}.json").write_text(json.dumps(raw), encoding="utf-8")
                        # Also copy index.json + epithets catalog so resolve sees them
                        src_idx = base_dir / "data" / "character_profiles" / "index.json"
                        if src_idx.exists():
                            (tgt_dir / "index.json").write_text(src_idx.read_text(encoding="utf-8"), encoding="utf-8")
                        src_cat = base_dir / "data" / "character_data"
                        if src_cat.exists():
                            (td_path / "data" / "character_data").mkdir(parents=True, exist_ok=True)
                            for f in src_cat.glob("*.json"):
                                (td_path / "data" / "character_data" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                        opted = character_profiles.resolve_profile(
                            card_id=card_id, scenario_id=4, base_dir=td_path,
                        )
                        self.assertGreater(
                            len(opted.auto_picked_epithets), 0,
                            f"{expected_id} signature must still be discoverable when user opts into auto-pick",
                        )


# --------------------------------------------------------------------------
# v6.6 -- regression test for the silent-drop bug in profile injection
# --------------------------------------------------------------------------


class SolverWeightInjectionTests(unittest.TestCase):
    """Reproduces the v6.2-v6.5 silent-drop bug and verifies the v6.6 fix.

    The bug: when a preset's mant_config.trackblazer_weights was populated
    with system defaults (which happened whenever the user clicked Save in
    the Smart Race Solver Settings dashboard panel), the runner's profile
    override injection silently dropped every profile override because the
    old condition treated 'default value' the same as 'user-set value'.

    The fix: profile override wins when the preset's value equals the
    system default (i.e. user didn't actually choose that value), and the
    user's explicit non-default choices still win over the profile.
    """

    def _simulate_injection_v66(self, weights, profile_overrides):
        """Mirror the v6.6 runner.py / races.py injection logic."""
        from career_bot.trackblazer import DEFAULT_SOLVER_WEIGHTS as _DEF
        for k, v in profile_overrides.items():
            current = weights.get(k)
            preset_default = _DEF.get(k)
            if k not in weights or current in (None, "", 0):
                weights[k] = v
            elif preset_default is not None and current == preset_default:
                weights[k] = v
            # else: preset has a non-default value -> preset wins
        return weights

    def test_profile_wins_when_preset_has_system_default(self):
        from career_bot.trackblazer import DEFAULT_SOLVER_WEIGHTS as _DEF
        preset_weights = dict(_DEF)  # Simulates dashboard Save
        profile_overrides = {
            "epithetValue": 3.0,
            "raceCostPct": 75.0,
            "longDistanceStaminaFloor": 450,
        }
        result = self._simulate_injection_v66(preset_weights, profile_overrides)
        self.assertEqual(result["epithetValue"], 3.0)
        self.assertEqual(result["raceCostPct"], 75.0)
        self.assertEqual(result["longDistanceStaminaFloor"], 450)

    def test_user_explicit_non_default_wins_over_profile(self):
        from career_bot.trackblazer import DEFAULT_SOLVER_WEIGHTS as _DEF
        preset_weights = dict(_DEF)
        # User explicitly raised epithetValue beyond default in the dashboard
        preset_weights["epithetValue"] = 5.0
        profile_overrides = {"epithetValue": 3.0, "raceCostPct": 75.0}
        result = self._simulate_injection_v66(preset_weights, profile_overrides)
        # User override wins
        self.assertEqual(result["epithetValue"], 5.0)
        # Profile still fills in the value the user didn't override
        self.assertEqual(result["raceCostPct"], 75.0)

    def test_profile_wins_on_empty_preset_weights(self):
        # The historical legacy case: preset has no trackblazer_weights at all
        preset_weights = {}
        profile_overrides = {"epithetValue": 3.0, "raceCostPct": 75.0}
        result = self._simulate_injection_v66(preset_weights, profile_overrides)
        self.assertEqual(result["epithetValue"], 3.0)
        self.assertEqual(result["raceCostPct"], 75.0)

    def test_oguri_v66_profile_now_has_real_levers(self):
        """v6.6 oguri_cap.json: targetOptionalRaceCount removed, real
        levers (epithetValue, raceCostPct, lateSeniorRacePressure)
        present."""
        base_dir = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base_dir)
        overrides = profile.solver_overrides
        self.assertNotIn("targetOptionalRaceCount", overrides,
                         "v6.6: targetOptionalRaceCount is a no-op, should not be in the profile")
        self.assertEqual(overrides.get("epithetValue"), 3.0)
        self.assertEqual(overrides.get("raceCostPct"), 75.0)
        self.assertEqual(overrides.get("lateSeniorRacePressure"), 20.0)


# --------------------------------------------------------------------------
# v6.4 -- auto-pick of signature epithets with user-override precedence
# --------------------------------------------------------------------------


class AutoPickEpithetsTests(unittest.TestCase):
    """``effective_target_epithets`` returns the right list and source label
    across the explicit > auto-pick > none chain."""

    def test_explicit_profile_target_wins_over_auto(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "display_name": "Oguri Cap",  # would auto-pick signature
                        "target_epithets": ["My Custom Goal"],
                    },
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            targets, source = profile.effective_target_epithets()
            self.assertEqual(targets, ["My Custom Goal"])
            self.assertEqual(source, "profile")

    def test_auto_picks_signature_when_target_empty_and_opted_in(self):
        # v6.7.6: auto_pick now defaults to OFF.  Tests that exercise
        # auto-pick behavior must explicitly enable it via the profile
        # JSON so they reflect the opt-in usage pattern.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"100601": "oguri_cap"}},
                {
                    "oguri_cap": {
                        "display_name": "Oguri Cap",
                        "auto_pick_epithets": True,
                    },
                    "default": {},
                },
            )
            # Seed a fake epithet catalog so auto-pick has something to
            # find for "Oguri Cap"
            epi_path = base / "data" / "character_data" / "epithets.json"
            epi_path.parent.mkdir(parents=True, exist_ok=True)
            epi_path.write_text(json.dumps({
                "Ideal Idol": {"name": "Ideal Idol", "characters": ["Oguri Cap"]},
            }), encoding="utf-8")
            profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base)
            targets, source = profile.effective_target_epithets()
            self.assertEqual(source, "auto")
            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0], "Ideal Idol")

    def test_auto_pick_can_be_disabled_in_profile(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "display_name": "Oguri Cap",
                        "auto_pick_epithets": False,
                    },
                    "default": {},
                },
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            targets, source = profile.effective_target_epithets()
            self.assertEqual(targets, [])
            self.assertEqual(source, "none")

    def test_auto_pick_can_be_disabled_per_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {
                    "x": {
                        "display_name": "Oguri Cap",
                        # base allows auto-pick (opt-in for this test)
                        "auto_pick_epithets": True,
                        "scenarios": {"4": {"auto_pick_epithets": False}},
                    },
                    "default": {},
                },
            )
            # Scenario 4 turns it off
            scen4 = character_profiles.resolve_profile(card_id=1, scenario_id=4, base_dir=base)
            self.assertFalse(scen4.auto_pick_epithets)
            # Scenario 1 still has it on
            scen1 = character_profiles.resolve_profile(card_id=1, scenario_id=1, base_dir=base)
            self.assertTrue(scen1.auto_pick_epithets)

    def test_auto_pick_default_is_false_v676(self):
        """v6.7.6: when neither the profile JSON nor any scenario block
        sets ``auto_pick_epithets``, the default is False (was True in
        v6.5-v6.7.5)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            write_profile_set(
                base,
                {"by_card_id": {"1": "x"}},
                {"x": {"display_name": "Test"}, "default": {}},
            )
            profile = character_profiles.resolve_profile(card_id=1, base_dir=base)
            self.assertFalse(profile.auto_pick_epithets,
                "v6.7.6 default for auto_pick_epithets is False (was True earlier)")

    def test_unknown_character_has_empty_auto_picks(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # No catalog in this empty temp dir, so auto-pick lookup returns []
            profile = character_profiles.resolve_profile(card_id=999999, base_dir=base)
            self.assertEqual(profile.auto_picked_epithets, [])
            targets, source = profile.effective_target_epithets()
            self.assertEqual(targets, [])
            self.assertEqual(source, "none")

    def _temp_dir_with_auto_pick_profile(self, td, profile_id, display_name, card_id):
        """Helper: build a temp base_dir with a single profile that has
        auto_pick_epithets=True and copies the shipped epithet catalog."""
        base = Path(td)
        write_profile_set(
            base,
            {"by_card_id": {str(card_id): profile_id}},
            {
                profile_id: {
                    "display_name": display_name,
                    "auto_pick_epithets": True,
                },
                "default": {},
            },
        )
        # Copy the shipped character_data catalog so signature lookup works
        shipped = Path(__file__).resolve().parent.parent / "data" / "character_data"
        if shipped.exists():
            tgt = base / "data" / "character_data"
            tgt.mkdir(parents=True, exist_ok=True)
            for f in shipped.glob("*.json"):
                (tgt / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        return base

    def test_oguri_auto_picks_ideal_idol(self):
        """Regression check: when auto-pick is OPTED IN, Oguri's signature
        epithet is 'Ideal Idol' (v6.7.6: opt-in is now required)."""
        with tempfile.TemporaryDirectory() as td:
            base = self._temp_dir_with_auto_pick_profile(td, "oguri_cap", "Oguri Cap", 100601)
            profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base)
            self.assertGreater(len(profile.auto_picked_epithets), 0)
            self.assertEqual(profile.auto_picked_epithets[0], "Ideal Idol")

    def test_special_week_auto_picks_signature(self):
        with tempfile.TemporaryDirectory() as td:
            base = self._temp_dir_with_auto_pick_profile(td, "special_week", "Special Week", 100101)
            profile = character_profiles.resolve_profile(card_id=100101, scenario_id=4, base_dir=base)
            self.assertGreater(len(profile.auto_picked_epithets), 0)
            self.assertTrue(profile.auto_picked_epithets[0])

    def test_auto_derived_path_also_gets_auto_picks(self):
        """A trainee with no hand-curated profile but a name match in the
        catalog should still get signature CANDIDATES discovered via the
        v6.3 auto-derivation path.  v6.7.6: the candidate list is still
        populated by catalog lookup, but ``auto_pick_epithets`` defaults
        to False so the candidates aren't INJECTED into the solver until
        the user opts in.  Verify both halves of the contract."""
        base = Path(__file__).resolve().parent.parent  # uses shipped catalog
        chara = make_chara(name="Mejiro McQueen", long_=8, medium=7, mile=5, sprint=2)
        profile = character_profiles.resolve_profile(
            card_id=999999, chara_id=999999, scenario_id=4,
            base_dir=base, chara_info=chara,
        )
        self.assertEqual(profile.matched_via, "auto")
        # Catalog candidates ARE discovered (the catalog still maps
        # Mejiro McQueen -> her signature epithet)
        self.assertGreater(
            len(profile.auto_picked_epithets), 0,
            "Catalog signature lookup should still resolve for auto-derived profiles",
        )
        # But the flag defaults to OFF in v6.7.6, so the effective
        # target list is empty
        self.assertFalse(profile.auto_pick_epithets)
        targets, source = profile.effective_target_epithets()
        self.assertEqual(targets, [])
        self.assertEqual(source, "none")

    def test_to_dict_includes_auto_pick_fields(self):
        """Verify the to_dict payload exposes the flag.  v6.7.6: with the
        default flipped, the flag now defaults to False on shipped
        profiles -- the test asserts the field is present, not its
        value."""
        base = Path(__file__).resolve().parent.parent
        profile = character_profiles.resolve_profile(card_id=100601, scenario_id=4, base_dir=base)
        d = profile.to_dict()
        self.assertIn("auto_pick_epithets", d)
        self.assertIn("auto_picked_epithets", d)
        # v6.7.6 default is False; profile JSON can opt in
        self.assertIsInstance(d["auto_pick_epithets"], bool)


if __name__ == "__main__":
    unittest.main()
