import json
import tempfile
import unittest
from pathlib import Path

from career_bot.config_store import ConfigStore
from career_bot.skills import SkillBuyer

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "public" / "app.js").read_text(encoding="utf-8")


class SweepyModV59ConfigSplitTests(unittest.TestCase):
    def test_legacy_per_file_preset_is_adopted_and_self_contained(self):
        # v7.6: data/presets/ is now the CANONICAL per-file store. A pre-existing
        # per-file preset is adopted in place (not split into global files and
        # deleted), and its settings/skill/solver layers stay readable.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "data" / "presets"
            legacy.mkdir(parents=True)
            (legacy / "Example.json").write_text(json.dumps({
                "name": "Example",
                "training_stat_priority": ["speed", "wit"],
                "mant_config": {"maximum_failure_chance": 15},
                "learn_skill_threshold": 430,
                "skill_strategy": {"forced_skills": ["Mile Maven"]},
                "trackblazer_target_epithets": ["Mile Queen"],
                "extra_race_list": [1001, 1002],
            }), encoding="utf-8")
            store = ConfigStore(base)
            # The per-file store persists; the legacy split files are NOT created.
            self.assertTrue((base / "data" / "presets").exists())
            self.assertTrue((base / "data" / "presets" / "Example.json").exists())
            self.assertFalse((base / "data" / "settings_presets.json").exists())
            settings = store.read_settings_presets()["presets"][0]
            self.assertIn("mant_config", settings)
            self.assertNotIn("learn_skill_threshold", settings)
            self.assertEqual(store.read_skill_config("Example")["learn_skill_threshold"], 430)
            self.assertEqual(store.read_solver_config("Example")["extra_race_list"], [1001, 1002])
            runtime = store.compose_runtime_preset("Example")
            self.assertEqual(runtime["mant_config"]["maximum_failure_chance"], 15)
            self.assertEqual(runtime["learn_skill_threshold"], 430)
            self.assertEqual(runtime["trackblazer_target_epithets"], ["Mile Queen"])

    def test_configure_skills_ui_replaces_old_tier_editor(self):
        self.assertIn('id="skill-config-launch-section"', INDEX)
        self.assertIn('id="skill-config-body"', INDEX)
        self.assertNotIn('id="skill-tiers-container"', INDEX)
        self.assertNotIn('id="skill-blacklist-container"', INDEX)
        self.assertIn('function renderSkillConfig', APP)
        self.assertIn('/api/skill-config', APP)
        self.assertIn('The number of skill points to accumulate before purchasing skills.', APP)

    def test_new_settings_presets_exclude_skill_and_solver_ui_storage(self):
        self.assertIn('id="settings-preset-section"', INDEX)
        self.assertIn('/api/settings-presets', APP)
        self.assertIn('/api/smart-solver/config', APP)
        self.assertNotIn('id="preset-section"', INDEX)
        self.assertNotIn('id="preset-skill-threshold"', INDEX)

    def test_skill_buyer_uses_threshold_as_purchase_gate_not_stop_reason(self):
        buyer = SkillBuyer(str(ROOT))
        state = {"data": {"chara_info": {"turn": 12, "skill_point": 300, "skill_tips_array": []}}}
        new_state, bought = buyer.buy(object(), state, {"learn_skill_threshold": 400, "enable_skill_point_check": True})
        self.assertIs(new_state, state)
        self.assertEqual(bought, 0)
        self.assertEqual(buyer.last_result.get("skip"), "threshold")
        self.assertEqual(buyer.last_result.get("threshold"), 400)

    def test_skill_point_check_can_be_disabled_without_stopping_runner(self):
        buyer = SkillBuyer(str(ROOT))
        state = {"data": {"chara_info": {"turn": 12, "skill_point": 2000, "skill_tips_array": []}}}
        _, bought = buyer.buy(object(), state, {"enable_skill_point_check": False})
        self.assertEqual(bought, 0)
        self.assertEqual(buyer.last_result.get("skip"), "skill_point_check_disabled")


if __name__ == "__main__":
    unittest.main()
