"""Tests for the live-policy promotion review + guarded promote (Idea #3).

The self-improvement loop already exists; this tool only gates the manual
promotion decision. We test the pure decision logic, the review renderer, and
a round-trip of the flag flip via the real auto-config I/O (redirected with
UMA_RUNTIME_DIR).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import promote_policy as pp  # noqa: E402
from career_bot import ai_trainer  # noqa: E402


class PromotionDecisionTests(unittest.TestCase):
    def test_allows_when_recommended(self):
        d = pp.promotion_decision({"recommend_enable": True, "enabled": False})
        self.assertTrue(d["allow"])
        self.assertEqual(d["action"], "promote")

    def test_blocks_when_not_recommended(self):
        d = pp.promotion_decision({"recommend_enable": False, "enabled": False})
        self.assertFalse(d["allow"])
        self.assertEqual(d["action"], "blocked")

    def test_force_overrides_block(self):
        d = pp.promotion_decision({"recommend_enable": False, "enabled": False}, force=True)
        self.assertTrue(d["allow"])
        self.assertEqual(d["action"], "promote_forced")

    def test_noop_when_already_enabled(self):
        d = pp.promotion_decision({"recommend_enable": True, "enabled": True})
        self.assertFalse(d["allow"])
        self.assertEqual(d["action"], "noop")


class RenderTests(unittest.TestCase):
    def test_review_renders_recommendation(self):
        status = {
            "auto_config": {"confidence_threshold": 0.65},
            "live_policy": {
                "enabled": False, "requested_enabled": False,
                "race_adjustments": 3, "item_adjustments": 0, "event_adjustments": 1,
                "confidence_threshold": 0.65,
                "recommendation": {
                    "recommend_enable": False,
                    "message": "Recommended: KEEP DISABLED. Not enough data.",
                    "reasons": ["Only 40 race rows are available."],
                },
            },
            "dataset_status": {"counts": {"turn_decisions": 120, "career_summaries": 3}},
        }
        out = pp.render_review(status, {"success": False, "detail": "none"},
                               {"success": False, "detail": "none"})
        self.assertIn("KEEP DISABLED", out)
        self.assertIn("Only 40 race rows", out)
        self.assertIn("--force", out)

    def test_review_renders_real_artifact_keys(self):
        # Field names match the real shadow_policy_report / backtest_report.
        status = {"live_policy": {"enabled": True, "requested_enabled": True,
                                  "recommendation": {"recommend_enable": True}},
                  "dataset_status": {}, "auto_config": {}}
        shadow = {"success": True, "precision": 0.9412, "evaluated_races": 8104,
                  "warnings": 153, "useful_warnings": 144, "false_alarms": 9}
        backtest = {"success": True, "capture_rate": 0.5269, "false_warning_rate": 0.7035,
                    "historical_race_rows": 8323, "risk_warnings": 2081}
        out = pp.render_review(status, shadow, backtest)
        self.assertIn("precision=94%", out)
        self.assertIn("useful=144", out)
        self.assertIn("false_alarms=9", out)
        self.assertIn("races=8323", out)


class FlagRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.runtime = Path(self.tmp) / "uma_runtime"
        os.environ["UMA_RUNTIME_DIR"] = str(self.runtime)

    def tearDown(self):
        os.environ.pop("UMA_RUNTIME_DIR", None)

    def test_promote_blocked_does_not_flip_flag(self):
        result = pp.apply_promotion(
            self.runtime, force=False,
            recommendation={"recommend_enable": False, "enabled": False})
        self.assertFalse(result["allow"])
        cfg = ai_trainer.load_auto_config(self.runtime)
        self.assertFalse(cfg.get("enable_live_policy_assistance"))

    def test_promote_recommended_flips_flag(self):
        result = pp.apply_promotion(
            self.runtime, force=False,
            recommendation={"recommend_enable": True, "enabled": False})
        self.assertTrue(result["allow"])
        self.assertTrue(result["enabled_now"])
        cfg = ai_trainer.load_auto_config(self.runtime)
        self.assertTrue(cfg.get("enable_live_policy_assistance"))

    def test_force_flips_flag_when_not_recommended(self):
        result = pp.apply_promotion(
            self.runtime, force=True,
            recommendation={"recommend_enable": False, "enabled": False})
        self.assertTrue(result["allow"])
        self.assertTrue(result["enabled_now"])

    def test_demote_flips_back(self):
        pp.apply_promotion(self.runtime, force=True,
                           recommendation={"recommend_enable": False, "enabled": False})
        result = pp.apply_demotion(self.runtime)
        self.assertFalse(result["enabled_now"])
        cfg = ai_trainer.load_auto_config(self.runtime)
        self.assertFalse(cfg.get("enable_live_policy_assistance"))


if __name__ == "__main__":
    unittest.main()
