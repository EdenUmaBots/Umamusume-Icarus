"""v7.6 — per-file preset store + preset-specific skill config.

Each preset is now one self-contained file under data/presets/ holding its
settings + skill + solver config, migrated from the legacy split layout
(settings_presets.json + global skill_config.json + smart_solver_config.json).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from career_bot.config_store import ConfigStore


class PerFilePresetStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.build = self.tmp / "build"      # base_dir (no data/, so no build migration)
        self.ud = self.tmp / "userdata"      # userdata_dir
        (self.ud / "data").mkdir(parents=True)
        self.build.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _store(self):
        return ConfigStore(self.build, userdata_dir=self.ud)

    def _seed_legacy(self):
        data = self.ud / "data"
        (data / "settings_presets.json").write_text(json.dumps({
            "active": "alpha",
            "presets": [
                {"name": "alpha", "running_style": 2, "mant_config": {"x": 1}},
                {"name": "beta", "running_style": 3},
            ],
        }), encoding="utf-8")
        (data / "skill_config.json").write_text(json.dumps(
            {"learn_skill_threshold": 1234, "skip_green_skills": True}), encoding="utf-8")
        (data / "smart_solver_config.json").write_text(json.dumps(
            {"extra_race_list": [100628]}), encoding="utf-8")

    def test_migration_creates_per_file_presets(self):
        self._seed_legacy()
        store = self._store()
        presets_dir = self.ud / "data" / "presets"
        files = sorted(p.name for p in presets_dir.glob("*.json"))
        self.assertEqual(files, ["alpha.json", "beta.json"])
        # legacy files backed up, not left to re-migrate
        self.assertTrue((self.ud / "data" / "settings_presets.json.premigrate.bak").exists())
        sp = store.read_settings_presets()
        self.assertEqual(sp["active"], "alpha")
        self.assertEqual({p["name"] for p in sp["presets"]}, {"alpha", "beta"})
        # formerly-global skill + solver folded into each preset
        store.set_active("alpha")
        self.assertEqual(store.read_skill_config()["learn_skill_threshold"], 1234)
        self.assertTrue(store.read_skill_config()["skip_green_skills"])
        self.assertEqual(store.read_solver_config()["extra_race_list"], [100628])

    def test_migration_is_idempotent(self):
        self._seed_legacy()
        self._store()
        # second instantiation must not re-import or duplicate
        store2 = self._store()
        files = sorted(p.name for p in (self.ud / "data" / "presets").glob("*.json"))
        self.assertEqual(files, ["alpha.json", "beta.json"])
        self.assertEqual({p["name"] for p in store2.read_settings_presets()["presets"]}, {"alpha", "beta"})

    def test_skill_config_is_per_preset(self):
        store = self._store()
        store.save_settings_preset({"name": "alpha"})
        store.save_settings_preset({"name": "beta"})
        store.set_active("alpha")
        store.save_skill_config({"learn_skill_threshold": 111})
        store.set_active("beta")
        store.save_skill_config({"learn_skill_threshold": 222})
        store.set_active("alpha")
        self.assertEqual(store.read_skill_config()["learn_skill_threshold"], 111)
        store.set_active("beta")
        self.assertEqual(store.read_skill_config()["learn_skill_threshold"], 222)

    def test_manual_tiers_are_per_preset(self):
        store = self._store()
        store.save_settings_preset({"name": "alpha"})
        store.save_settings_preset({"name": "beta"})
        store.set_active("alpha")
        store.save_skill_config({"manual_skill_tiers": {"1": ["Professor of Curvature"]}})
        store.set_active("beta")
        self.assertEqual(store.read_skill_config()["manual_skill_tiers"]["1"], [])
        store.set_active("alpha")
        self.assertEqual(store.read_skill_config()["manual_skill_tiers"]["1"], ["Professor of Curvature"])

    def test_compose_runtime_has_all_layers(self):
        store = self._store()
        store.save_settings_preset({"name": "alpha", "running_style": 2})
        store.set_active("alpha")
        store.save_skill_config({"learn_skill_threshold": 999})
        store.save_solver_config({"extra_race_list": [1, 2, 3]})
        rt = store.compose_runtime_preset("alpha")
        self.assertEqual(rt.get("running_style"), 2)
        self.assertEqual(rt.get("learn_skill_threshold"), 999)
        self.assertEqual(rt.get("extra_race_list"), [1, 2, 3])
        self.assertEqual(rt.get("name"), "alpha")

    def test_fresh_install_creates_default(self):
        store = self._store()
        sp = store.read_settings_presets()
        self.assertTrue(sp["presets"])
        self.assertTrue((self.ud / "data" / "presets" / "default.json").exists()
                        or any(p.name.lower() == "default.json" for p in (self.ud / "data" / "presets").glob("*.json")))

    def test_delete_preset(self):
        store = self._store()
        store.save_settings_preset({"name": "alpha"})
        store.save_settings_preset({"name": "beta"})
        store.delete_settings_preset("beta")
        names = {p["name"] for p in store.read_settings_presets()["presets"]}
        self.assertNotIn("beta", names)


if __name__ == "__main__":
    unittest.main()
