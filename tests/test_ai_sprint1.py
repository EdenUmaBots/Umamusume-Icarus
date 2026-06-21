"""Tests for the Sprint 1 AI advisor improvements.

Covers:
  - career_bot.ai_modeling   (BetaPosterior, hierarchical pooling, scoring)
  - career_bot.calibration   (reliability diagram, ECE, isotonic, PAV fallback)

Plus a small contract test for ``career_bot.ai_advisor.race_program_hint``
to confirm the legacy return shape is preserved across the v1 -> v2 swap.
"""

from __future__ import annotations

import json
import os
import random
import tempfile
import unittest
from pathlib import Path

from career_bot.ai_modeling import (
    BetaPosterior,
    HierarchicalLevel,
    global_base_rate,
    hierarchical_posterior,
    posterior_from_stats_bucket,
    score_program,
)
from career_bot.calibration import (
    IsotonicCalibrator,
    brier_score,
    expected_calibration_error,
    extract_race_predictions,
    reliability_diagram,
)


# ---------------------------------------------------------------------------
# BetaPosterior
# ---------------------------------------------------------------------------


class BetaPosteriorTests(unittest.TestCase):
    def test_from_prior_centers_on_mean(self):
        p = BetaPosterior.from_prior(prior_mean=0.7, prior_strength=10.0)
        self.assertAlmostEqual(p.mean(), 0.7, places=6)
        self.assertAlmostEqual(p.alpha + p.beta, 10.0, places=6)

    def test_jeffreys_is_half_half(self):
        j = BetaPosterior.jeffreys()
        self.assertEqual(j.alpha, 0.5)
        self.assertEqual(j.beta, 0.5)

    def test_update_accumulates_counts(self):
        p = BetaPosterior.from_prior(0.5, 2.0).update(wins=3, losses=1)
        self.assertAlmostEqual(p.alpha, 1.0 + 3.0)
        self.assertAlmostEqual(p.beta, 1.0 + 1.0)

    def test_update_one_dispatches_by_outcome(self):
        p = BetaPosterior.jeffreys().update_one(True).update_one(False)
        self.assertAlmostEqual(p.alpha, 1.5)
        self.assertAlmostEqual(p.beta, 1.5)

    def test_negative_updates_rejected(self):
        with self.assertRaises(ValueError):
            BetaPosterior(1, 1).update(wins=-1, losses=0)

    def test_lcb_is_below_mean_below_ucb(self):
        p = BetaPosterior.from_prior(0.5, 4.0).update(wins=10, losses=4)
        lcb = p.lcb(0.25)
        ucb = p.ucb(0.75)
        self.assertLess(lcb, p.mean())
        self.assertGreater(ucb, p.mean())
        self.assertLess(lcb, ucb)

    def test_credible_interval_contains_mass(self):
        p = BetaPosterior.from_prior(0.5, 4.0).update(wins=8, losses=2)
        lo, hi = p.credible_interval(mass=0.9)
        self.assertLess(lo, p.mean())
        self.assertGreater(hi, p.mean())

    def test_variance_collapses_with_data(self):
        prior = BetaPosterior.from_prior(0.5, 2.0)
        many = prior.update(wins=200, losses=200)
        self.assertGreater(prior.variance(), many.variance())

    def test_round_trip_serialization(self):
        p = BetaPosterior.from_prior(0.3, 6.0).update(2, 7)
        clone = BetaPosterior.from_dict(p.to_dict())
        self.assertEqual(p, clone)


# ---------------------------------------------------------------------------
# Stats-bucket bridge + global base rate
# ---------------------------------------------------------------------------


class StatsBridgeTests(unittest.TestCase):
    def test_posterior_from_bucket_with_explicit_wins(self):
        bucket = {"starts": 10, "wins": 7, "win_rate": 0.7}
        p = posterior_from_stats_bucket(bucket, prior=BetaPosterior.jeffreys())
        # Jeffreys prior + 7 wins, 3 losses
        self.assertAlmostEqual(p.alpha, 0.5 + 7)
        self.assertAlmostEqual(p.beta, 0.5 + 3)

    def test_posterior_from_bucket_reconstructs_wins_from_rate(self):
        bucket = {"starts": 10, "win_rate": 0.4}  # no explicit wins
        p = posterior_from_stats_bucket(bucket, prior=BetaPosterior.jeffreys())
        self.assertAlmostEqual(p.alpha, 0.5 + 4)
        self.assertAlmostEqual(p.beta, 0.5 + 6)

    def test_posterior_clamps_wins_to_starts(self):
        # Corrupted bucket where wins > starts shouldn't crash or produce
        # negative losses.
        bucket = {"starts": 5, "wins": 99}
        p = posterior_from_stats_bucket(bucket, prior=BetaPosterior.jeffreys())
        self.assertAlmostEqual(p.alpha, 0.5 + 5)  # capped at starts
        self.assertAlmostEqual(p.beta, 0.5 + 0)

    def test_global_base_rate_falls_back_below_min_starts(self):
        races = {"100": {"starts": 2, "wins": 1, "win_rate": 0.5}}
        self.assertEqual(global_base_rate(races, min_total_starts=10), 0.5)

    def test_global_base_rate_uses_pooled_when_enough_data(self):
        races = {
            "100": {"starts": 50, "wins": 30},
            "200": {"starts": 50, "wins": 10},
        }
        rate = global_base_rate(races, min_total_starts=10)
        self.assertAlmostEqual(rate, 40 / 100)


# ---------------------------------------------------------------------------
# Hierarchical pooling
# ---------------------------------------------------------------------------


class HierarchicalPosteriorTests(unittest.TestCase):
    def test_empty_levels_returns_prior(self):
        post, contributed = hierarchical_posterior([], prior_mean=0.3)
        self.assertEqual(contributed, [])
        self.assertAlmostEqual(post.mean(), 0.3, places=6)

    def test_single_level_matches_direct_update(self):
        bucket = {"starts": 10, "wins": 6}
        post, contributed = hierarchical_posterior(
            [HierarchicalLevel("program", 100, bucket)],
            prior_mean=0.5,
            prior_strength=4.0,
            parent_discount=0.0,  # no carryover -> base prior applied at leaf
        )
        # With discount=0 the leaf sees the base prior, then updates with 6/4.
        expected = BetaPosterior.from_prior(0.5, 4.0).update(6, 4)
        self.assertEqual(contributed, ["program"])
        self.assertAlmostEqual(post.alpha, expected.alpha, places=6)
        self.assertAlmostEqual(post.beta, expected.beta, places=6)

    def test_sparse_child_inherits_from_parent(self):
        # The child level has very few observations.  With strong parent
        # carryover the child's posterior should look more like the parent's
        # than like the child's raw rate.
        parent_bucket = {"starts": 100, "wins": 70}     # parent looks ~70% win
        child_bucket = {"starts": 2, "wins": 0}          # child is 0/2
        post_strong, _ = hierarchical_posterior(
            [
                HierarchicalLevel("program", 100, parent_bucket),
                HierarchicalLevel("program_char", (100, 7), child_bucket),
            ],
            prior_mean=0.5,
            prior_strength=4.0,
            parent_discount=1.0,  # full carryover from parent
        )
        # With full carryover, child's 0/2 should not crash the mean to ~0.
        self.assertGreater(post_strong.mean(), 0.5)

    def test_no_carryover_isolates_child(self):
        parent_bucket = {"starts": 100, "wins": 70}
        child_bucket = {"starts": 2, "wins": 0}
        post_iso, _ = hierarchical_posterior(
            [
                HierarchicalLevel("program", 100, parent_bucket),
                HierarchicalLevel("program_char", (100, 7), child_bucket),
            ],
            prior_mean=0.5,
            prior_strength=4.0,
            parent_discount=0.0,  # no carryover
        )
        # Child sees only the base prior + 0/2 -> mean below 0.5
        self.assertLess(post_iso.mean(), 0.5)


# ---------------------------------------------------------------------------
# Scoring: replacing the -8.0 magic number
# ---------------------------------------------------------------------------


class ScoringTests(unittest.TestCase):
    def test_score_program_returns_all_expected_keys(self):
        p = BetaPosterior.from_prior(0.5, 4.0).update(5, 5)
        out = score_program(p, avg_reward=10.0)
        for key in ("adjustment", "lcb", "ucb", "mean", "variance", "alpha", "beta"):
            self.assertIn(key, out)

    def test_low_winrate_yields_low_adjustment(self):
        low = BetaPosterior.from_prior(0.5, 4.0).update(1, 9)
        high = BetaPosterior.from_prior(0.5, 4.0).update(9, 1)
        low_score = score_program(low, avg_reward=10.0)["adjustment"]
        high_score = score_program(high, avg_reward=10.0)["adjustment"]
        self.assertLess(low_score, high_score)

    def test_no_data_yields_modest_adjustment_no_discontinuity(self):
        """The big v1 problem: a discontinuous -8.0 jump at win_rate=0.5.
        Verify the new score moves smoothly through that region."""
        scores = []
        for wins in range(11):
            p = BetaPosterior.from_prior(0.5, 4.0).update(wins, 10 - wins)
            scores.append(score_program(p, avg_reward=10.0)["adjustment"])
        # Strictly increasing in wins, no big jumps
        for prev, nxt in zip(scores, scores[1:]):
            self.assertGreater(nxt, prev)
            self.assertLess(nxt - prev, 4.0)  # no v1-style discontinuity


# ---------------------------------------------------------------------------
# Calibration: reliability, ECE, Brier, isotonic
# ---------------------------------------------------------------------------


class CalibrationTests(unittest.TestCase):
    def test_empty_inputs_are_safe(self):
        self.assertEqual(reliability_diagram([]), [])
        self.assertEqual(expected_calibration_error([]), 0.0)
        self.assertEqual(brier_score([]), 0.0)

    def test_perfect_calibration_has_near_zero_ece(self):
        # Build predictions where bin midpoints exactly match outcomes.
        rng = random.Random(42)
        preds = []
        for _ in range(2000):
            p = rng.random()
            outcome = rng.random() < p
            preds.append((p, outcome))
        ece = expected_calibration_error(preds, n_bins=10)
        self.assertLess(ece, 0.05)

    def test_anti_calibration_has_high_ece(self):
        # Predict 0.9 but win 10% of the time.
        preds = [(0.9, False)] * 90 + [(0.9, True)] * 10
        ece = expected_calibration_error(preds, n_bins=10)
        self.assertGreater(ece, 0.5)

    def test_brier_of_uniform_guess(self):
        preds = [(0.5, True), (0.5, False)] * 100
        self.assertAlmostEqual(brier_score(preds), 0.25, places=4)

    def test_isotonic_improves_miscalibrated_predictions(self):
        # Systematically overconfident: emit p but true rate is p^2.
        rng = random.Random(7)
        train = []
        for _ in range(3000):
            raw = rng.random()
            true_p = raw ** 2
            train.append((raw, rng.random() < true_p))

        before = expected_calibration_error(train, n_bins=10)
        calibrator = IsotonicCalibrator().fit(train)

        # Generate a fresh test set with the same distribution
        test = []
        for _ in range(3000):
            raw = rng.random()
            true_p = raw ** 2
            test.append((raw, rng.random() < true_p))

        after = [
            (calibrator.transform_one(p), y) for p, y in test
        ]
        after_ece = expected_calibration_error(after, n_bins=10)
        self.assertLess(after_ece, before)
        self.assertLess(after_ece, 0.05)

    def test_isotonic_roundtrips_through_dict(self):
        rng = random.Random(1)
        preds = [(rng.random(), rng.random() < 0.5) for _ in range(500)]
        cal = IsotonicCalibrator().fit(preds)
        payload = cal.to_dict()
        restored = IsotonicCalibrator.from_dict(payload)
        # Both produce the same output for a fixed input.
        for q in (0.1, 0.25, 0.5, 0.75, 0.9):
            self.assertAlmostEqual(
                cal.transform_one(q), restored.transform_one(q), places=3
            )

    def test_extract_race_predictions_filters_non_races(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "turn_decisions.jsonl"
            rows = [
                # race row, has prediction, wins
                {
                    "action": {"type": "race", "program_id": 100},
                    "decision_report": {"predicted_win_prob": 0.7},
                    "outcome": {"race_result": {"rank": 1}},
                },
                # non-race row, should be skipped
                {
                    "action": {"type": "train_speed"},
                    "decision_report": {"predicted_win_prob": 0.9},
                    "outcome": {},
                },
                # race row without prediction, skipped
                {
                    "action": {"type": "race", "program_id": 200},
                    "decision_report": {},
                    "outcome": {"race_result": {"rank": 3}},
                },
                # race row falling back to race_context.win_rate
                {
                    "action": {"type": "race", "program_id": 300},
                    "decision_report": {"race_context": {"win_rate": 0.4}},
                    "outcome": {"race_result": {"rank": 5}},
                },
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            preds = extract_race_predictions(path)
            self.assertEqual(len(preds), 2)
            self.assertEqual(preds[0], (0.7, True))
            self.assertEqual(preds[1], (0.4, False))


# ---------------------------------------------------------------------------
# Backward-compat contract for race_program_hint
# ---------------------------------------------------------------------------


class RaceProgramHintContractTests(unittest.TestCase):
    """The existing call sites in runner.py and the v532 test consume these
    exact field names.  The v2 swap must not remove any of them."""

    LEGACY_FIELDS = {
        "program_id", "confidence", "starts",
        "win_rate", "avg_reward", "adjustment", "reason",
    }
    NEW_FIELDS = {
        "posterior_mean", "lcb", "ucb", "variance", "alpha", "beta",
    }

    def setUp(self):
        self._prior_env = os.environ.get("UMA_RUNTIME_DIR")

    def tearDown(self):
        if self._prior_env is None:
            os.environ.pop("UMA_RUNTIME_DIR", None)
        else:
            os.environ["UMA_RUNTIME_DIR"] = self._prior_env

    def _runtime_with_stats(self, tmp: Path, payload: dict) -> Path:
        runtime = tmp / "uma_runtime"
        ai = runtime / "ai"
        ai.mkdir(parents=True, exist_ok=True)
        (ai / "advisor_stats.json").write_text(json.dumps(payload), encoding="utf-8")
        # runtime_output_root() walks parents looking for .git; in a temp
        # directory it falls back to base.parent / "uma_runtime" which is
        # wrong for tests.  The UMA_RUNTIME_DIR env override is the
        # documented escape hatch.
        os.environ["UMA_RUNTIME_DIR"] = str(runtime)
        return tmp

    def test_cold_start_returns_all_fields(self):
        from career_bot.ai_advisor import race_program_hint
        with tempfile.TemporaryDirectory() as tmp:
            base = self._runtime_with_stats(Path(tmp), {"race_programs": {}})
            hint = race_program_hint(base, 99901)
            self.assertEqual(hint["confidence"], "none")
            self.assertEqual(hint["adjustment"], 0.0)
            for key in self.LEGACY_FIELDS | self.NEW_FIELDS:
                self.assertIn(key, hint, f"missing field: {key}")

    def test_observed_program_uses_posterior_math(self):
        from career_bot.ai_advisor import race_program_hint
        with tempfile.TemporaryDirectory() as tmp:
            base = self._runtime_with_stats(Path(tmp), {
                "race_programs": {
                    "99901": {"starts": 10, "wins": 7, "win_rate": 0.7,
                              "avg_reward": 5.0},
                }
            })
            hint = race_program_hint(base, 99901)
            self.assertEqual(hint["starts"], 10)
            self.assertAlmostEqual(hint["win_rate"], 0.7)
            self.assertIn(hint["confidence"], {"low", "medium", "high"})
            # Adjustment = avg_reward * LCB, so should be positive but
            # bounded above by avg_reward * UCB.
            self.assertGreater(hint["adjustment"], 0)
            self.assertLess(hint["adjustment"], 5.0)
            # New fields populated
            self.assertGreater(hint["posterior_mean"], 0.5)
            self.assertLess(hint["lcb"], hint["posterior_mean"])

    def test_low_winrate_no_longer_jumps_minus_eight(self):
        """The v1 behavior: starts >= 3 and win_rate < 0.5 -> adjustment -= 8.
        The v2 adjustment must move smoothly with no discontinuity."""
        from career_bot.ai_advisor import race_program_hint
        adjustments = []
        for wins in range(0, 11):
            with tempfile.TemporaryDirectory() as tmp:
                base = self._runtime_with_stats(Path(tmp), {
                    "race_programs": {
                        "99901": {"starts": 10, "wins": wins,
                                  "win_rate": wins / 10, "avg_reward": 10.0},
                    }
                })
                hint = race_program_hint(base, 99901)
                adjustments.append(hint["adjustment"])
        # Strictly increasing, no jumps > 4 between adjacent points
        for prev, nxt in zip(adjustments, adjustments[1:]):
            self.assertGreater(nxt, prev)
            self.assertLess(nxt - prev, 4.0)


if __name__ == "__main__":
    unittest.main()
