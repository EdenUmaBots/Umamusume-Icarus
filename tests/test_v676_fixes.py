"""Regression tests for v6.7.6:
  1. Sparks bug: ``_extract_final_chara_payload`` now resolves the just-
     finished trainee from ``trained_chara`` using ``trained_chara_id``
     instead of taking the first array entry.
  2. Userdata directory: ConfigStore routes settings/skill/solver JSON
     to an external userdata folder when provided, and migrates
     existing in-build files on first run.
  3. Auto-pick default: ``auto_pick_epithets`` defaults to False per
     v6.7.6 user request; profile JSON with the field set still wins.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Stub native deps that aren't available in the sandbox
for _modname in ("msgpack",):
    if _modname not in sys.modules:
        sys.modules[_modname] = MagicMock()


# --- 1. Sparks fix ----------------------------------------------------------

class SparksExtractionTests(unittest.TestCase):
    """Confirm the v6.7.6 fix: factor_info_array comes from the entry
    in trained_chara whose trained_chara_id matches the top-level id,
    not from trained_chara[0] (which is always a parent slot)."""

    def setUp(self):
        from career_bot.runner import CareerRunner
        self.runner = CareerRunner.__new__(CareerRunner)
        self.runner._walk_dicts = lambda data: []  # stub catch-all walk

    def _finish_payload(self, just_finished_id, just_finished_factors, other_entries):
        """Build a minimal finish-state payload matching the game's shape."""
        trained_chara = list(other_entries)
        trained_chara.append({
            "trained_chara_id": just_finished_id,
            "card_id": 100601,
            "factor_info_array": [{"factor_id": fid} for fid in just_finished_factors],
        })
        return {
            "data": {
                "single_mode_finish_common": {
                    "trained_chara_id": just_finished_id,
                    "trained_chara": trained_chara,
                },
            },
        }

    def test_resolves_just_finished_entry_not_first(self):
        """Different ``trained_chara_id`` values must produce different
        factor arrays.  Before the fix, both calls returned the parent
        slot at index 0 (identical sparks)."""
        # Two parent entries at the start (these were the bug source --
        # the old code picked these up as the trainee).
        parent_a = {"trained_chara_id": 100, "card_id": 999001,
                    "factor_info_array": [{"factor_id": 999}]}
        parent_b = {"trained_chara_id": 101, "card_id": 999002,
                    "factor_info_array": [{"factor_id": 888}]}

        # Run 1: trained_chara_id=2953 with factors [201, 3202, ...]
        payload_a = self._finish_payload(2953, [201, 3202, 1000802], [parent_a, parent_b])
        merged_a = self.runner._extract_final_chara_payload(payload_a, {})
        ids_a = [r.get("factor_id") for r in merged_a.get("factor_info_array") or []]

        # Run 2: trained_chara_id=2954 with DIFFERENT factors [202, 3403, ...]
        payload_b = self._finish_payload(2954, [202, 3403, 2007202], [parent_a, parent_b])
        merged_b = self.runner._extract_final_chara_payload(payload_b, {})
        ids_b = [r.get("factor_id") for r in merged_b.get("factor_info_array") or []]

        # The bug: ids_a == ids_b == [999] (parent_a's factors).
        # The fix: ids_a != ids_b, and each matches the just-finished entry.
        self.assertNotEqual(ids_a, ids_b, "factor_info_array must differ between runs")
        self.assertIn(201, ids_a)
        self.assertNotIn(201, ids_b)
        self.assertIn(202, ids_b)
        # Parent factor 999 must NOT appear -- it's not the trainee's
        self.assertNotIn(999, ids_a)
        self.assertNotIn(999, ids_b)


# --- 2. Userdata directory --------------------------------------------------

class UserdataConfigStoreTests(unittest.TestCase):
    """ConfigStore writes settings/skill/solver JSON to userdata when
    a userdata_dir is provided, and migrates in-build defaults forward."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.build_dir = self.tmp / "SweepyClaudev6.7.6"
        self.user_dir = self.tmp / "SweepyClaude_userdata"
        (self.build_dir / "data").mkdir(parents=True)
        # Seed an in-build settings_presets.json that should migrate
        (self.build_dir / "data" / "settings_presets.json").write_text(json.dumps({
            "active": "MyCustom",
            "presets": [{"name": "MyCustom", "scenario_id": 4}],
        }), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_userdata_dir_receives_settings(self):
        from career_bot.config_store import ConfigStore
        cs = ConfigStore(str(self.build_dir), userdata_dir=str(self.user_dir))
        # Config now lives under userdata as per-file presets (v7.6).
        self.assertEqual(cs.data_dir, self.user_dir / "data")
        self.assertTrue((self.user_dir / "data" / "presets").exists())
        self.assertTrue((self.user_dir / "data" / "presets" / "MyCustom.json").exists())

    def test_migration_copies_existing_settings(self):
        from career_bot.config_store import ConfigStore
        cs = ConfigStore(str(self.build_dir), userdata_dir=str(self.user_dir))
        # The user's "MyCustom" preset is carried forward into the per-file store.
        payload = cs.read_settings_presets()
        self.assertEqual(payload["active"], "MyCustom")
        self.assertIn("MyCustom", {p["name"] for p in payload["presets"]})

    def test_userdata_none_uses_in_build_path(self):
        """When userdata_dir is None or equals base_dir, behavior is the
        legacy in-build path (no migration triggered)."""
        from career_bot.config_store import ConfigStore
        cs = ConfigStore(str(self.build_dir))
        self.assertEqual(cs.data_dir, self.build_dir / "data")
        # No userdata folder should have been created
        self.assertFalse(self.user_dir.exists())

    def test_userdata_preserves_user_changes_on_upgrade(self):
        """User presets in userdata must survive a build upgrade that ships
        a different default."""
        from career_bot.config_store import ConfigStore
        cs = ConfigStore(str(self.build_dir), userdata_dir=str(self.user_dir))
        # User adds/customizes a preset through the store.
        cs.save_settings_preset({"name": "UserEdited", "scenario_id": 4})
        self.assertEqual(cs.read_settings_presets()["active"], "UserEdited")
        # Simulate an upgrade: re-init with a NEW build shipping a different default.
        new_build = self.tmp / "SweepyClaudev7.7"
        (new_build / "data").mkdir(parents=True)
        (new_build / "data" / "settings_presets.json").write_text(json.dumps({
            "active": "NewDefault", "presets": [{"name": "NewDefault"}],
        }), encoding="utf-8")
        cs2 = ConfigStore(str(new_build), userdata_dir=str(self.user_dir))
        # The user's customization survives (per-file store already migrated).
        payload = cs2.read_settings_presets()
        self.assertEqual(payload["active"], "UserEdited")
        self.assertIn("UserEdited", {p["name"] for p in payload["presets"]})


# --- 3. Auto-pick default ---------------------------------------------------

class AutoPickDefaultTests(unittest.TestCase):
    def _make_profile(self, **overrides):
        from career_bot.character_profiles import CharacterProfile
        defaults = dict(
            profile_id="test",
            display_name="Test",
            matched_via="fallback",
            scenario_id=4,
        )
        defaults.update(overrides)
        return CharacterProfile(**defaults)

    def test_dataclass_default_is_false(self):
        p = self._make_profile()
        self.assertFalse(p.auto_pick_epithets, "v6.7.6 default flipped from True to False")

    def test_profile_json_can_opt_in(self):
        """A profile JSON with auto_pick_epithets: true must still
        enable the bias.  Verifies the dataclass default doesn't block
        explicit user/profile opt-in."""
        p = self._make_profile(auto_pick_epithets=True)
        self.assertTrue(p.auto_pick_epithets)


if __name__ == "__main__":
    unittest.main()
